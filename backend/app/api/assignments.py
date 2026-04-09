from __future__ import annotations

import csv
import datetime as dt
import io
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Teacher, Assignment, Group, Quiz, Attempt, Answer, AssignmentStudentView
from app.api.deps import get_current_teacher
from app.schemas.schemas import (
    AssignmentCreate, AssignmentUpdate, AssignmentOut,
    AssignmentResultsSummary, StudentResultRow, ShareCodeLookup,
    AttemptResult, ResultQuestionDetail, OptionOutTeacher, SavedAnswer,
)

router = APIRouter(prefix="/api/assignments", tags=["assignments"])
_STUDENT_VIEW_MODES = {"closed", "attempt", "results"}


def _get_student_view_mode(a: Assignment) -> str:
    mode = a.student_view.student_view_mode if a.student_view else ("results" if a.results_visible else "closed")
    if mode not in _STUDENT_VIEW_MODES:
        return "closed"
    return mode


def _set_student_view_mode(a: Assignment, db: Session, mode: str) -> None:
    if mode not in _STUDENT_VIEW_MODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid student_view_mode")
    if a.student_view is None:
        db.add(AssignmentStudentView(assignment_id=a.id, student_view_mode=mode))
    else:
        a.student_view.student_view_mode = mode
    # Keep legacy flag in sync for backward compatibility.
    a.results_visible = mode == "results"


def _assignment_to_out(a: Assignment) -> AssignmentOut:
    mode = _get_student_view_mode(a)
    return AssignmentOut(
        id=a.id,
        quiz_id=a.quiz_id,
        group_id=a.group_id,
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        duration_minutes=a.duration_minutes,
        time_limit_minutes=a.time_limit_minutes,
        results_visible=mode == "results",
        student_view_mode=mode,
        quiz_title=a.quiz.title,
        group_name=a.group.name,
        share_code=a.share_code,
    )


def _fmt_dt_csv(value: dt.datetime | None) -> str:
    if value is None:
        return ""
    v = value.replace(tzinfo=None) if value.tzinfo else value
    return f"{v.isoformat()}Z"


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(
    body: AssignmentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    quiz = db.get(Quiz, body.quiz_id)
    if quiz is None or quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    group = db.get(Group, body.group_id)
    if group is None or group.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")

    starts = body.starts_at.replace(tzinfo=None) if body.starts_at.tzinfo else body.starts_at
    ends = starts + dt.timedelta(minutes=body.duration_minutes)

    tlm = body.time_limit_minutes if body.time_limit_minutes is not None else quiz.time_limit_minutes
    if not tlm or tlm <= 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Time limit is required (set in quiz file or assignment form)",
        )
    assignment = Assignment(
        quiz_id=body.quiz_id,
        group_id=body.group_id,
        starts_at=starts,
        ends_at=ends,
        duration_minutes=body.duration_minutes,
        time_limit_minutes=tlm,
        share_code=secrets.token_urlsafe(6),
    )
    db.add(assignment)
    db.flush()
    db.add(AssignmentStudentView(assignment_id=assignment.id, student_view_mode="closed"))
    db.commit()
    db.refresh(assignment)
    return _assignment_to_out(assignment)


@router.get("", response_model=list[AssignmentOut])
def list_assignments(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignments = (
        db.query(Assignment)
        .join(Quiz)
        .filter(Quiz.teacher_id == teacher.id)
        .order_by(Assignment.starts_at.desc(), Assignment.id.desc())
        .all()
    )
    return [_assignment_to_out(a) for a in assignments]


@router.patch("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    body: AssignmentUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    starts_at_changed = False
    if body.student_view_mode is not None:
        _set_student_view_mode(assignment, db, body.student_view_mode)
    elif body.results_visible is not None:
        _set_student_view_mode(assignment, db, "results" if body.results_visible else "closed")
    if body.starts_at is not None:
        new_starts = body.starts_at.replace(tzinfo=None) if body.starts_at.tzinfo else body.starts_at
        starts_at_changed = new_starts != assignment.starts_at
        assignment.starts_at = new_starts
    if body.duration_minutes is not None:
        assignment.duration_minutes = body.duration_minutes
        assignment.ends_at = assignment.starts_at + dt.timedelta(minutes=assignment.duration_minutes)
    elif starts_at_changed:
        # Keep schedule consistency when starts_at changes by itself.
        assignment.ends_at = assignment.starts_at + dt.timedelta(minutes=assignment.duration_minutes)
    if body.time_limit_minutes is not None:
        assignment.time_limit_minutes = body.time_limit_minutes

    if starts_at_changed:
        # Teacher explicitly requested that changing starts_at aborts open attempts.
        unfinished_attempts = (
            db.query(Attempt)
            .filter(Attempt.assignment_id == assignment.id, Attempt.submitted_at.is_(None))
            .all()
        )
        for att in unfinished_attempts:
            db.delete(att)

    db.commit()
    db.refresh(assignment)
    return _assignment_to_out(assignment)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    db.delete(assignment)
    db.commit()


@router.get("/by-code/{code}", response_model=ShareCodeLookup)
def lookup_by_share_code(code: str, db: Session = Depends(get_db)):
    assignment = db.query(Assignment).filter(Assignment.share_code == code).first()
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return ShareCodeLookup(
        assignment_id=assignment.id,
        quiz_title=assignment.quiz.title,
    )


@router.get("/{assignment_id}/results", response_model=AssignmentResultsSummary)
def get_assignment_results(
    assignment_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    max_score = sum(q.points for q in assignment.quiz.questions)
    attempts = db.query(Attempt).filter(Attempt.assignment_id == assignment_id).all()

    from app.api.students import _auto_grade_expired
    for att in attempts:
        if not att.submitted_at:
            _auto_grade_expired(att, db)

    results = []
    for att in attempts:
        if att.submitted_at:
            st = "submitted"
        else:
            st = "in_progress"
        results.append(StudentResultRow(
            student_id=att.student_id,
            attempt_id=att.id,
            student_name=att.student.display_name,
            score=att.score,
            submitted_at=att.submitted_at,
            status=st,
        ))

    return AssignmentResultsSummary(
        assignment_id=assignment.id,
        quiz_title=assignment.quiz.title,
        group_name=assignment.group.name,
        max_score=max_score,
        results=results,
    )


@router.get("/{assignment_id}/attempts/{attempt_id}", response_model=AttemptResult)
def get_attempt_detail_teacher(
    assignment_id: int,
    attempt_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.assignment_id != assignment_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")

    quiz = assignment.quiz
    max_score = sum(q.points for q in quiz.questions)
    answers_map = {a.question_id: a for a in attempt.answers}

    question_details = []
    for q in quiz.questions:
        ans = answers_map.get(q.id)
        correct_ids = [o.id for o in q.options if o.is_correct]
        question_details.append(ResultQuestionDetail(
            question_id=q.id,
            title=q.title,
            q_type=q.q_type,
            points=q.points,
            points_awarded=ans.points_awarded if ans else 0,
            is_correct=ans.is_correct if ans else False,
            selected_option_ids=ans.selected_option_ids if ans else None,
            text_answer=ans.text_answer if ans else None,
            correct_option_ids=correct_ids if correct_ids else None,
            accepted_answers=q.accepted_answers,
            explanation_md=q.explanation_md,
            options=[OptionOutTeacher.model_validate(o) for o in q.options],
            body_md=q.body_md,
        ))

    return AttemptResult(
        attempt_id=attempt.id,
        student_name=attempt.student.display_name,
        score=attempt.score,
        max_score=max_score,
        student_view_mode="results",
        submitted_at=attempt.submitted_at,
        questions=question_details,
    )


@router.get("/{assignment_id}/results.csv")
def export_assignment_results_csv(
    assignment_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.quiz.teacher_id != teacher.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    attempts = db.query(Attempt).filter(Attempt.assignment_id == assignment_id).all()
    from app.api.students import _auto_grade_expired
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for att in attempts:
        if not att.submitted_at:
            _auto_grade_expired(att, db, now=now)

    # Re-read attempts after possible auto-grading mutations.
    attempts = db.query(Attempt).filter(Attempt.assignment_id == assignment_id).all()
    questions = list(assignment.quiz.questions)
    max_score = sum(q.points for q in questions)

    output = io.StringIO()
    writer = csv.writer(output)
    header = [
        "student_id",
        "student_login",
        "attempt_id",
        "status",
        "score",
        "max_score",
        "correct_answers_count",
        "total_questions",
        "submitted_at",
    ] + [f"q{idx + 1}_correct" for idx, _ in enumerate(questions)]
    writer.writerow(header)

    for att in attempts:
        answers_map = {a.question_id: a for a in att.answers}
        per_question: list[str] = []
        correct_answers_count = 0
        for q in questions:
            ans = answers_map.get(q.id)
            if ans is None or ans.is_correct is None:
                per_question.append("")
                continue
            if ans.is_correct:
                correct_answers_count += 1
                per_question.append("1")
            else:
                per_question.append("0")

        row = [
            att.student_id,
            att.student.username,
            att.id,
            "submitted" if att.submitted_at else "in_progress",
            "" if att.score is None else f"{att.score:g}",
            max_score,
            correct_answers_count,
            len(questions),
            _fmt_dt_csv(att.submitted_at),
        ] + per_question
        writer.writerow(row)

    filename = f'assignment_{assignment_id}_results.csv'
    csv_content = "\ufeff" + output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
