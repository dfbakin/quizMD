from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    quizzes: Mapped[list[Quiz]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    groups: Mapped[list[Group]] = relationship(back_populates="teacher", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)

    teacher: Mapped[Teacher] = relationship(back_populates="groups")
    students: Mapped[list[Student]] = relationship(back_populates="group", cascade="all, delete-orphan")
    assignments: Mapped[list[Assignment]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)

    group: Mapped[Group] = relationship(back_populates="students")
    attempts: Mapped[list[Attempt]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_md: Mapped[str] = mapped_column(Text, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    shuffle_answers: Mapped[bool] = mapped_column(Boolean, default=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    teacher: Mapped[Teacher] = relationship(back_populates="quizzes")
    questions: Mapped[list[Question]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="Question.order_index"
    )
    assignments: Mapped[list[Assignment]] = relationship(back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    q_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_answers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=1)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    options: Mapped[list[Option]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Option.order_index"
    )


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text_md: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    question: Mapped[Question] = relationship(back_populates="options")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    # Denormalized: ends_at == starts_at + start_window_minutes. It's the
    # *start window* close, not the per-attempt deadline.
    ends_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    # How long after starts_at a student may begin an attempt. Decoupled from
    # duration_minutes so a teacher can, e.g. open a 30-minute quiz for a
    # 90-minute window and still give every student the full 30 minutes once
    # they actually start.
    start_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # How long the attempt itself runs once started. Snapshotted into
    # Attempt.deadline_at at start; subsequent edits do not affect attempts in
    # flight unless the teacher chooses Reset.
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # When True, every attempt's snapshotted deadline is anchored to
    # ``starts_at + duration_minutes`` (a single wall-clock cutoff for the
    # whole group) instead of ``started_at + duration_minutes``. Late starters
    # therefore have less time on the clock — the trade-off the teacher
    # explicitly opted into. Implies start_window_minutes == duration_minutes.
    shared_deadline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    results_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    share_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="assignments")
    group: Mapped[Group] = relationship(back_populates="assignments")
    attempts: Mapped[list[Attempt]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    student_view: Mapped[AssignmentStudentView | None] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", uselist=False
    )


class AssignmentStudentView(Base):
    __tablename__ = "assignment_student_views"

    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), primary_key=True)
    student_view_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="closed")

    assignment: Mapped[Assignment] = relationship(back_populates="student_view")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    shuffle_seed: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # Snapshot deadline computed at start = started_at + assignment.duration_minutes.
    # Immune to subsequent edits of the parent Assignment.
    deadline_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped[Student] = relationship(back_populates="attempts")
    assignment: Mapped[Assignment] = relationship(back_populates="attempts")
    answers: Mapped[list[Answer]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    selected_option_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    text_answer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
