"""Shared API dependencies (auth, DB session)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.models import Teacher, Student

_bearer = HTTPBearer()


def _get_token_payload(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    try:
        return decode_access_token(creds.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_current_teacher(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> Teacher:
    if payload.get("role") != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teacher access required")
    teacher = db.get(Teacher, int(payload["sub"]))
    if teacher is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Teacher not found")
    return teacher


def get_current_student(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> Student:
    if payload.get("role") != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student access required")
    student = db.get(Student, int(payload["sub"]))
    if student is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Student not found")
    return student
