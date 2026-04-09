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
    ends_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
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
