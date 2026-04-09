"""Student quiz-taking endpoints: list assignments, start, save, submit, results."""

from __future__ import annotations

import datetime as dt
import random
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student, Assignment, Attempt, Answer, Question
from app.api.deps import get_current_student
from app.services.grader import grade_answer
from app.schemas.schemas import (
    StudentAssignmentOut,
    AttemptStart,
    SavedAnswer,
    QuestionOut,
    OptionOut,
    AttemptSaveRequest,
    AttemptSubmitRequest,
    AttemptResult,
    ResultQuestionDetail,
    OptionOutTeacher,
)

router = APIRouter(tags=["student"])


def _utcnow() -> dt.datetime:
    """Return current UTC time as a naive datetime (for SQLite compat)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _ensure_naive(d: dt.datetime) -> dt.datetime:
    """Strip tzinfo if present so comparisons with naive datetimes work."""
    return d.replace(tzinfo=None) if d.tzinfo else d


def _assignment_time_limit_minutes(assignment: Assignment) -> int | None:
    return assignment.time_limit_minutes or assignment.quiz.time_limit_minutes


def _attempt_deadline(attempt: Attempt) -> dt.datetime:
    """Hybrid rule: min(attempt started + time limit, assignment end)."""
    assignment_end = _ensure_naive(attempt.assignment.ends_at)
    tlm = _assignment_time_limit_minutes(attempt.assignment)
    if tlm and tlm > 0:
        by_attempt_limit = _ensure_naive(attempt.started_at) + dt.timedelta(minutes=tlm)
        return min(by_attempt_limit, assignment_end)
    return assignment_end


def _is_attempt_expired(attempt: Attempt, now: dt.datetime) -> bool:
    return now > _attempt_deadline(attempt)


@router.get("/api/my/assignments", response_model=list[StudentAssignmentOut])
def list_my_assignments(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    now = _utcnow()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.group_id == student.group_id)
        .order_by(Assignment.starts_at.desc())
        .all()
    )
    result = []
    for a in assignments:
        attempt = (
            db.query(Attempt)
            .filter(Attempt.assignment_id == a.id, Attempt.student_id == student.id)
            .first()
        )
        tlm = _assignment_time_limit_minutes(a)
        attempt_expired = False
        if attempt and not attempt.submitted_at:
            attempt_expired = _is_attempt_expired(attempt, now)

        if now < _ensure_naive(a.starts_at):
            s = "upcoming"
        elif attempt and attempt.submitted_at:
            s = "completed"
        elif attempt_expired:
            s = "completed"
        elif now > _ensure_naive(a.ends_at):
            s = "completed"
        else:
            s = "active"

        result.append(StudentAssignmentOut(
            assignment_id=a.id,
            quiz_title=a.quiz.title,
            starts_at=a.starts_at,
            ends_at=a.ends_at,
            duration_minutes=a.duration_minutes,
            time_limit_minutes=tlm,
            status=s,
            attempt_id=attempt.id if attempt else None,
            results_visible=a.results_visible,
        ))
    return result


@router.post("/api/assignments/{assignment_id}/start", response_model=AttemptStart)
def start_attempt(
    assignment_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.group_id != student.group_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")

    now = _utcnow()
    if now < _ensure_naive(assignment.starts_at):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Quiz has not started yet")
    if now > _ensure_naive(assignment.ends_at):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Quiz deadline has passed")

    existing = (
        db.query(Attempt)
        .filter(Attempt.assignment_id == assignment_id, Attempt.student_id == student.id)
        .first()
    )
    if existing and existing.submitted_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

    tlm = _assignment_time_limit_minutes(assignment)

    if existing:
        if _is_attempt_expired(existing, now):
            _auto_grade_expired(existing, db, now=now)
            raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

        new_token = uuid.uuid4().hex
        existing.session_token = new_token
        db.commit()
        db.refresh(existing)

        questions = _get_shuffled_questions(assignment, existing.shuffle_seed, db)
        saved = [
            SavedAnswer(
                question_id=a.question_id,
                selected_option_ids=a.selected_option_ids,
                text_answer=a.text_answer,
            )
            for a in existing.answers
        ]
        return AttemptStart(
            attempt_id=existing.id,
            session_token=new_token,
            questions=questions,
            time_limit_minutes=tlm,
            started_at=existing.started_at,
            deadline_at=_attempt_deadline(existing),
            server_now=now,
            saved_answers=saved,
        )

    session_token = uuid.uuid4().hex
    shuffle_seed = uuid.uuid4().hex
    attempt = Attempt(
        student_id=student.id,
        assignment_id=assignment_id,
        session_token=session_token,
        shuffle_seed=shuffle_seed,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    questions = _get_shuffled_questions(assignment, shuffle_seed, db)
    return AttemptStart(
        attempt_id=attempt.id,
        session_token=session_token,
        questions=questions,
        time_limit_minutes=tlm,
        started_at=attempt.started_at,
        deadline_at=_attempt_deadline(attempt),
        server_now=now,
        saved_answers=[],
    )


def _auto_grade_expired(attempt: Attempt, db: Session, *, now: dt.datetime | None = None) -> None:
    """Grade saved answers and mark as submitted for expired attempts."""
    if attempt.submitted_at:
        return
    now = now or _utcnow()
    deadline = _attempt_deadline(attempt)
    if now <= deadline:
        return

    for answer in attempt.answers:
        question = db.get(Question, answer.question_id)
        if question is None:
            continue
        correct_ids = [o.id for o in question.options if o.is_correct]
        result = grade_answer(
            q_type=question.q_type,
            selected_option_ids=answer.selected_option_ids,
            correct_option_ids=correct_ids if correct_ids else None,
            text_answer=answer.text_answer,
            accepted_answers=question.accepted_answers,
            points=question.points,
        )
        answer.is_correct = result.is_correct
        answer.points_awarded = result.points_awarded

    total = sum(a.points_awarded for a in attempt.answers)
    attempt.submitted_at = deadline
    attempt.score = total
    db.commit()


def _verify_session_token(attempt: Attempt, token: str | None) -> None:
    if not token or token != attempt.session_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid session token")


def _get_shuffled_questions(
    assignment: Assignment, seed: str, db: Session,
) -> list[QuestionOut]:
    quiz = assignment.quiz
    questions = list(quiz.questions)

    rng = random.Random(seed)
    if quiz.shuffle_questions:
        rng.shuffle(questions)

    result = []
    for idx, q in enumerate(questions):
        options = list(q.options)
        if quiz.shuffle_answers and q.q_type in ("single", "multiple"):
            rng.shuffle(options)

        result.append(QuestionOut(
            id=q.id,
            order_index=idx,
            q_type=q.q_type,
            title=q.title,
            body_md=q.body_md,
            points=q.points,
            options=[OptionOut(id=o.id, order_index=i, text_md=o.text_md) for i, o in enumerate(options)],
        ))
    return result


@router.post("/api/attempts/{attempt_id}/save", status_code=200)
def save_answers(
    attempt_id: int,
    body: AttemptSaveRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    x_session_token: str | None = Header(None),
):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    _verify_session_token(attempt, x_session_token)
    if attempt.submitted_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")
    now = _utcnow()
    if _is_attempt_expired(attempt, now):
        _auto_grade_expired(attempt, db, now=now)
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

    _upsert_answers(attempt, body.answers, db, grade=False)
    return {"status": "saved"}


@router.post("/api/attempts/{attempt_id}/submit", status_code=200)
def submit_attempt(
    attempt_id: int,
    body: AttemptSubmitRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    x_session_token: str | None = Header(None),
):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    _verify_session_token(attempt, x_session_token)
    if attempt.submitted_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

    now = _utcnow()
    if _is_attempt_expired(attempt, now):
        _auto_grade_expired(attempt, db, now=now)
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

    _upsert_answers(attempt, body.answers, db, grade=True)
    db.refresh(attempt)
    attempt.submitted_at = now
    attempt.score = sum(a.points_awarded for a in attempt.answers)
    db.commit()

    return {"status": "submitted", "score": attempt.score}


def _upsert_answers(
    attempt: Attempt,
    answers_data: list,
    db: Session,
    *,
    grade: bool,
) -> None:
    existing_map = {a.question_id: a for a in attempt.answers}

    for ans in answers_data:
        question = db.get(Question, ans.question_id)
        if question is None:
            continue

        if ans.question_id in existing_map:
            answer = existing_map[ans.question_id]
            answer.selected_option_ids = ans.selected_option_ids
            answer.text_answer = ans.text_answer
        else:
            answer = Answer(
                attempt_id=attempt.id,
                question_id=ans.question_id,
                selected_option_ids=ans.selected_option_ids,
                text_answer=ans.text_answer,
            )
            db.add(answer)

        if grade:
            correct_ids = [o.id for o in question.options if o.is_correct]
            result = grade_answer(
                q_type=question.q_type,
                selected_option_ids=ans.selected_option_ids,
                correct_option_ids=correct_ids if correct_ids else None,
                text_answer=ans.text_answer,
                accepted_answers=question.accepted_answers,
                points=question.points,
            )
            answer.is_correct = result.is_correct
            answer.points_awarded = result.points_awarded

    db.commit()


@router.get("/api/attempts/{attempt_id}/results", response_model=AttemptResult)
def get_attempt_results(
    attempt_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")

    assignment = attempt.assignment
    if not assignment.results_visible:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Results not released yet")

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
        submitted_at=attempt.submitted_at,
        questions=question_details,
    )
