from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from pydantic import BaseModel, PlainSerializer


def _utc_ser(v: dt.datetime) -> str:
    s = v.isoformat()
    return s + "Z" if v.tzinfo is None and not s.endswith("Z") else s


UTCDatetime = Annotated[dt.datetime, PlainSerializer(_utc_ser, return_type=str)]
StudentViewMode = Literal["closed", "attempt", "results"]


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
    # How long after starts_at a student may begin an attempt. When omitted,
    # the server defaults it to ``duration_minutes`` — same semantics as
    # before the start window was decoupled from the attempt clock.
    # Ignored (forced equal to duration_minutes) when shared_deadline=True.
    start_window_minutes: int | None = None
    # How long the attempt itself runs once started.
    duration_minutes: int
    # When True, every attempt's deadline is anchored to ``starts_at + duration``
    # (single shared cutoff), instead of ``started_at + duration``. Late
    # starters therefore have less time on the clock.
    shared_deadline: bool = False


# When PATCHing starts_at on an assignment with active in-progress attempts, the teacher
# must explicitly choose how to handle them: "reset" runs the existing cascade-delete
# ("restart the quiz" workflow); "keep" leaves them with their snapshot deadline intact.
OnOpenAttempts = Literal["reset", "keep"]


class AssignmentUpdate(BaseModel):
    results_visible: bool | None = None
    student_view_mode: StudentViewMode | None = None
    starts_at: dt.datetime | None = None
    start_window_minutes: int | None = None
    duration_minutes: int | None = None
    shared_deadline: bool | None = None
    on_open_attempts: OnOpenAttempts | None = None


class AssignmentOut(BaseSchema):
    id: int
    quiz_id: int
    group_id: int
    starts_at: UTCDatetime
    # ends_at == starts_at + start_window_minutes (denormalized).
    ends_at: UTCDatetime
    start_window_minutes: int
    duration_minutes: int
    shared_deadline: bool = False
    results_visible: bool
    student_view_mode: StudentViewMode = "closed"
    quiz_title: str
    group_name: str
    share_code: str
    in_progress_attempts: int = 0

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
    duration_minutes: int
    started_at: UTCDatetime
    deadline_at: UTCDatetime
    server_now: UTCDatetime
    saved_answers: list[SavedAnswer]


class HeartbeatRequest(BaseModel):
    """
    Optional payload for /attempts/:id/heartbeat. When `answers` is omitted the
    heartbeat is purely a timer re-anchor; when provided, answers are upserted
    (same shape as /save) so a single round-trip handles both.
    """
    answers: list[SavedAnswer] | None = None


class HeartbeatResponse(BaseSchema):
    server_now: UTCDatetime
    deadline_at: UTCDatetime
    status: Literal["in_progress", "submitted", "expired"]
    expired: bool
    score: float | None = None


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
    student_view_mode: StudentViewMode = "results"
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
    # ends_at == starts_at + start_window_minutes — i.e. when the *Start*
    # button stops being clickable. Once an attempt is in progress, the
    # per-attempt deadline (`attempt_deadline_at`) takes over.
    ends_at: UTCDatetime
    start_window_minutes: int
    duration_minutes: int
    # Surfaced so the dashboard can label the deadline differently in shared
    # mode (where ends_at is also the per-attempt cutoff for everyone).
    shared_deadline: bool = False
    status: str
    attempt_id: int | None = None
    attempt_deadline_at: UTCDatetime | None = None
    results_visible: bool = False
    student_view_mode: StudentViewMode = "closed"


class ShareCodeLookup(BaseSchema):
    assignment_id: int
    quiz_title: str
