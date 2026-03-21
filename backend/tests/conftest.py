"""Shared fixtures for all backend tests."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Teacher, Student, Group, Quiz, Question, Option, Assignment
from app.auth.passwords import hash_password

TEST_DB_URL = "sqlite://"


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def app_client(db: Session):
    """FastAPI TestClient with DB dependency overridden."""
    from fastapi.testclient import TestClient
    from app.main import app

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_test_teacher(db: Session, username: str = "teacher1", password: str = "pass123") -> Teacher:
    teacher = Teacher(
        username=username,
        password_hash=hash_password(password),
        display_name=username.title(),
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def create_test_group(db: Session, teacher_id: int, name: str = "11А") -> Group:
    group = Group(name=name, teacher_id=teacher_id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def create_test_student(
    db: Session, group_id: int, username: str = "student01", password: str = "quiz2026",
) -> Student:
    student = Student(
        username=username,
        password_hash=hash_password(password),
        display_name=username.title(),
        group_id=group_id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


SAMPLE_QUIZ_MD = """\
---
title: "Тестовый квиз"
time_limit: 10
shuffle_questions: false
shuffle_answers: false
---

### Вопрос 1

Текст вопроса?

- [ ] A
- [x] B
- [ ] C

> Пояснение.

---

### Вопрос 2

Множественный?

- [x] X
- [x] Y
- [ ] Z

---

### Вопрос 3

Краткий?

answer: 42

> 42.
"""


def create_test_quiz(db: Session, teacher_id: int) -> Quiz:
    from app.services.quiz_importer import import_quiz
    return import_quiz(SAMPLE_QUIZ_MD, teacher_id, db)


def create_test_assignment(
    db: Session,
    quiz_id: int,
    group_id: int,
    starts_at: dt.datetime | None = None,
    duration_minutes: int = 60,
    time_limit_minutes: int | None = 10,
) -> Assignment:
    import secrets
    now = dt.datetime.now(dt.timezone.utc)
    start = starts_at or now - dt.timedelta(minutes=5)
    assignment = Assignment(
        quiz_id=quiz_id,
        group_id=group_id,
        starts_at=start,
        ends_at=start + dt.timedelta(minutes=duration_minutes),
        duration_minutes=duration_minutes,
        time_limit_minutes=time_limit_minutes,
        results_visible=False,
        share_code=secrets.token_urlsafe(6),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment
