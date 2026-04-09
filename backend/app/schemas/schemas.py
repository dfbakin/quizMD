from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from pydantic import BaseModel, PlainSerializer


def _utc_ser(v: dt.datetime) -> str:
    s = v.isoformat()
    return s + "Z" if v.tzinfo is None and not s.endswith("Z") else s


UTCDatetime = Annotated[dt.datetime, PlainSerializer(_utc_ser, return_type=str)]


class BaseSchema(BaseModel):
    """Response base — use UTCDatetime for datetime fields to get Z suffix."""
    pass


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    display_name: str


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

class OptionOut(BaseSchema):
    id: int
    order_index: int
    text_md: str

    model_config = {"from_attributes": True}


class OptionOutTeacher(OptionOut):
    is_correct: bool


class QuestionOut(BaseSchema):
    id: int
    order_index: int
    q_type: str
    title: str
    body_md: str
    points: int
    options: list[OptionOut]

    model_config = {"from_attributes": True}


class QuestionOutTeacher(BaseSchema):
    id: int
    order_index: int
    q_type: str
    title: str
    body_md: str
    explanation_md: str | None
    accepted_answers: list[str] | None
    points: int
    options: list[OptionOutTeacher]

    model_config = {"from_attributes": True}


class QuizSummary(BaseSchema):
    id: int
    title: str
    time_limit_minutes: int | None
    shuffle_questions: bool
    shuffle_answers: bool
    question_count: int
    created_at: UTCDatetime

    model_config = {"from_attributes": True}


class QuizDetail(QuizSummary):
    questions: list[QuestionOutTeacher]
    source_md: str


# ---------------------------------------------------------------------------
# Groups & Students
# ---------------------------------------------------------------------------

class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseSchema):
    id: int
    name: str
    student_count: int

    model_config = {"from_attributes": True}


class StudentCreate(BaseModel):
    username: str
    password: str
    display_name: str


class StudentBulkCreate(BaseModel):
    students: list[StudentCreate]


class StudentUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None


class StudentOut(BaseSchema):
    id: int
    username: str
    display_name: str
    group_id: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

class AssignmentCreate(BaseModel):
    quiz_id: int
    group_id: int
    starts_at: dt.datetime
    duration_minutes: int
    time_limit_minutes: int | None = None


class AssignmentUpdate(BaseModel):
    results_visible: bool | None = None
    starts_at: dt.datetime | None = None
    duration_minutes: int | None = None
    time_limit_minutes: int | None = None


class AssignmentOut(BaseSchema):
    id: int
    quiz_id: int
    group_id: int
    starts_at: UTCDatetime
    ends_at: UTCDatetime
    duration_minutes: int
    time_limit_minutes: int | None
    results_visible: bool
    quiz_title: str
    group_name: str
    share_code: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Student quiz-taking
# ---------------------------------------------------------------------------

class SavedAnswer(BaseModel):
    question_id: int
    selected_option_ids: list[int] | None = None
    text_answer: str | None = None


class AttemptStart(BaseSchema):
    attempt_id: int
    session_token: str
    questions: list[QuestionOut]
    time_limit_minutes: int | None
    started_at: UTCDatetime
    deadline_at: UTCDatetime
    server_now: UTCDatetime
    saved_answers: list[SavedAnswer]


class AnswerSave(BaseModel):
    question_id: int
    selected_option_ids: list[int] | None = None
    text_answer: str | None = None


class AttemptSaveRequest(BaseModel):
    answers: list[AnswerSave]


class AttemptSubmitRequest(BaseModel):
    answers: list[AnswerSave]


class ResultQuestionDetail(BaseSchema):
    question_id: int
    title: str
    q_type: str
    points: int
    points_awarded: int
    is_correct: bool | None
    selected_option_ids: list[int] | None
    text_answer: str | None
    correct_option_ids: list[int] | None = None
    accepted_answers: list[str] | None = None
    explanation_md: str | None = None
    options: list[OptionOutTeacher] | None = None
    body_md: str | None = None


class AttemptResult(BaseSchema):
    attempt_id: int
    student_name: str
    score: float | None
    max_score: int
    submitted_at: UTCDatetime | None
    questions: list[ResultQuestionDetail]


class StudentResultRow(BaseSchema):
    student_id: int
    attempt_id: int
    student_name: str
    score: float | None
    submitted_at: UTCDatetime | None
    status: str


class AssignmentResultsSummary(BaseSchema):
    assignment_id: int
    quiz_title: str
    group_name: str
    max_score: int
    results: list[StudentResultRow]


class StudentAssignmentOut(BaseSchema):
    assignment_id: int
    quiz_title: str
    starts_at: UTCDatetime
    ends_at: UTCDatetime
    duration_minutes: int
    time_limit_minutes: int | None
    status: str
    attempt_id: int | None = None
    results_visible: bool = False


class ShareCodeLookup(BaseSchema):
    assignment_id: int
    quiz_title: str
