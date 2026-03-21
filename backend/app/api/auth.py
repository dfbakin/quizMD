from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Teacher, Student
from app.auth.passwords import verify_password
from app.auth.jwt import create_access_token
from app.schemas.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.username == body.username).first()
    if teacher and verify_password(body.password, teacher.password_hash):
        token = create_access_token({"sub": str(teacher.id), "role": "teacher"})
        return TokenResponse(
            access_token=token, role="teacher",
            user_id=teacher.id, display_name=teacher.display_name,
        )

    student = db.query(Student).filter(Student.username == body.username).first()
    if student and verify_password(body.password, student.password_hash):
        token = create_access_token({"sub": str(student.id), "role": "student"})
        return TokenResponse(
            access_token=token, role="student",
            user_id=student.id, display_name=student.display_name,
        )

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
