from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Teacher, Group, Student
from app.api.deps import get_current_teacher
from app.auth.passwords import hash_password
from app.schemas.schemas import (
    GroupCreate, GroupOut, StudentCreate, StudentBulkCreate, StudentOut,
    StudentSearchOut, StudentUpdate,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])

# Second router for teacher-scoped "my …" endpoints that aren't nested under a
# specific group (e.g. searching students across all groups the teacher owns).
# Kept in this file so all the teacher↔student glue stays in one place.
my_router = APIRouter(prefix="/api/my", tags=["teacher"])


@my_router.get("/students", response_model=list[StudentSearchOut])
def search_my_students(
    q: str | None = Query(default=None, description="Case-insensitive substring match on display_name or username"),
    limit: int = Query(default=20, ge=1, le=100),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Autocomplete for 'add extra student' across every group the teacher owns.

    We join on Group to enforce teacher-ownership in SQL (no chance of leaking
    another teacher's students even if the filter below misfires). ``q`` is
    optional so callers can just preload the first N.
    """
    base = (
        db.query(Student, Group)
        .join(Group, Group.id == Student.group_id)
        .filter(Group.teacher_id == teacher.id)
    )
    if q:
        pattern = f"%{q.strip()}%"
        base = base.filter(
            or_(
                Student.display_name.ilike(pattern),
                Student.username.ilike(pattern),
            )
        )

    rows = (
        base
        .order_by(Student.display_name.asc(), Student.id.asc())
        .limit(limit)
        .all()
    )
    return [
        StudentSearchOut(
            id=s.id,
            username=s.username,
            display_name=s.display_name,
            group_id=g.id,
            group_name=g.name,
        )
        for s, g in rows
    ]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = Group(name=body.name, teacher_id=teacher.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupOut(id=group.id, name=group.name, student_count=0)


@router.get("", response_model=list[GroupOut])
def list_groups(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    groups = db.query(Group).filter(Group.teacher_id == teacher.id).all()
    return [GroupOut(id=g.id, name=g.name, student_count=len(g.students)) for g in groups]


@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return GroupOut(id=group.id, name=group.name, student_count=len(group.students))


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    db.delete(group)
    db.commit()


@router.get("/{group_id}/students", response_model=list[StudentOut])
def list_students(
    group_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return [StudentOut.model_validate(s) for s in group.students]


@router.delete("/{group_id}/students/{student_id}", status_code=204)
def delete_student(
    group_id: int,
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    student = db.get(Student, student_id)
    if student is None or student.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    db.delete(student)
    db.commit()


@router.patch("/{group_id}/students/{student_id}", response_model=StudentOut)
def update_student(
    group_id: int,
    student_id: int,
    body: StudentUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    student = db.get(Student, student_id)
    if student is None or student.group_id != group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")

    if body.display_name is None and body.password is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No changes provided")
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Display name cannot be empty")
        student.display_name = name
    if body.password is not None:
        if not body.password:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Password cannot be empty")
        student.password_hash = hash_password(body.password)

    db.commit()
    db.refresh(student)
    return StudentOut.model_validate(student)


@router.post("/{group_id}/students", response_model=list[StudentOut], status_code=201)
def add_students(
    group_id: int,
    body: StudentBulkCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")

    created = []
    for s in body.students:
        existing = db.query(Student).filter(Student.username == s.username).first()
        if existing:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Username '{s.username}' already exists",
            )
        student = Student(
            username=s.username,
            password_hash=hash_password(s.password),
            display_name=s.display_name,
            group_id=group_id,
        )
        db.add(student)
        created.append(student)

    db.commit()
    for s in created:
        db.refresh(s)
    return [StudentOut.model_validate(s) for s in created]
