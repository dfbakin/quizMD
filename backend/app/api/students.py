"""Student quiz-taking endpoints: list assignments, start, save, submit, results."""

from __future__ import annotations

import datetime as dt
import random
import threading
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
    HeartbeatRequest,
    HeartbeatResponse,
)

router = APIRouter(tags=["student"])
_STUDENT_VIEW_MODES = {"closed", "attempt", "results"}
_ATTEMPT_START_LOCKS: dict[tuple[int, int], threading.Lock] = {}
_ATTEMPT_START_LOCKS_GUARD = threading.Lock()


def _utcnow() -> dt.datetime:
    """Return current UTC time as a naive datetime (for SQLite compat)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _ensure_naive(d: dt.datetime) -> dt.datetime:
    """Strip tzinfo if present so comparisons with naive datetimes work."""
    return d.replace(tzinfo=None) if d.tzinfo else d


def _attempt_deadline(attempt: Attempt) -> dt.datetime:
    """The per-attempt deadline is snapshotted at start. Read it directly."""
    return _ensure_naive(attempt.deadline_at)


def _is_attempt_expired(attempt: Attempt, now: dt.datetime) -> bool:
    return now > _attempt_deadline(attempt)


def _attempt_status(attempt: Attempt, now: dt.datetime) -> str:
    if attempt.submitted_at is not None:
        return "submitted"
    if _is_attempt_expired(attempt, now):
        return "expired"
    return "in_progress"


def _student_view_mode(assignment: Assignment) -> str:
    mode = assignment.student_view.student_view_mode if assignment.student_view else ("results" if assignment.results_visible else "closed")
    if mode not in _STUDENT_VIEW_MODES:
        return "closed"
    return mode


def _attempt_start_lock(student_id: int, assignment_id: int) -> threading.Lock:
    key = (student_id, assignment_id)
    with _ATTEMPT_START_LOCKS_GUARD:
        lock = _ATTEMPT_START_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _ATTEMPT_START_LOCKS[key] = lock
        return lock


def _pick_primary_attempt(attempts: list[Attempt]) -> Attempt:
    submitted = [a for a in attempts if a.submitted_at]
    if submitted:
        return max(
            submitted,
            key=lambda a: (_ensure_naive(a.submitted_at) if a.submitted_at else dt.datetime.min, a.id),
        )
    # If duplicate unfinished attempts exist, keep the one with most progress.
    return max(attempts, key=lambda a: (len(a.answers), _ensure_naive(a.started_at), a.id))


def _load_primary_attempt(
    db: Session,
    *,
    assignment_id: int,
    student_id: int,
    cleanup_duplicates: bool,
) -> Attempt | None:
    attempts = (
        db.query(Attempt)
        .filter(Attempt.assignment_id == assignment_id, Attempt.student_id == student_id)
        .order_by(Attempt.id.asc())
        .all()
    )
    if not attempts:
        return None

    primary = _pick_primary_attempt(attempts)
    if cleanup_duplicates and len(attempts) > 1:
        for att in attempts:
            if att.id != primary.id:
                db.delete(att)
        db.commit()
        refreshed = db.get(Attempt, primary.id)
        if refreshed is None:
            return None
        primary = refreshed

    return primary


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
        attempts = (
            db.query(Attempt)
            .filter(Attempt.assignment_id == a.id, Attempt.student_id == student.id)
            .order_by(Attempt.id.asc())
            .all()
        )
        attempt = _pick_primary_attempt(attempts) if attempts else None
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
            # Start window closed; if no attempt was ever started the assignment is over.
            s = "completed"
        else:
            s = "active"

        result.append(StudentAssignmentOut(
            assignment_id=a.id,
            quiz_title=a.quiz.title,
            starts_at=a.starts_at,
            ends_at=a.ends_at,
            start_window_minutes=a.start_window_minutes,
            duration_minutes=a.duration_minutes,
            shared_deadline=a.shared_deadline,
            status=s,
            attempt_id=attempt.id if attempt else None,
            attempt_deadline_at=attempt.deadline_at if attempt else None,
            results_visible=_student_view_mode(a) == "results",
            student_view_mode=_student_view_mode(a),
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
    # ends_at == starts_at + start_window_minutes is the close of the *start*
    # window. Once an attempt has begun, only its own snapshot deadline_at
    # matters; ends_at no longer applies.
    if now > _ensure_naive(assignment.ends_at):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Quiz deadline has passed")

    lock = _attempt_start_lock(student.id, assignment_id)
    with lock:
        existing = _load_primary_attempt(
            db,
            assignment_id=assignment_id,
            student_id=student.id,
            cleanup_duplicates=True,
        )
        if existing and existing.submitted_at:
            raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

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
                duration_minutes=assignment.duration_minutes,
                started_at=existing.started_at,
                deadline_at=_attempt_deadline(existing),
                server_now=now,
                saved_answers=saved,
            )

        session_token = uuid.uuid4().hex
        shuffle_seed = uuid.uuid4().hex
        # Snapshot deadline at creation time so subsequent edits to the parent
        # Assignment cannot move it.
        #   shared_deadline=True  → anchor to starts_at (every attempt of this
        #                           assignment ends at the same wall-clock).
        #   shared_deadline=False → anchor to started_at (each student gets the
        #                           full per-attempt clock from when they began).
        anchor = (
            _ensure_naive(assignment.starts_at)
            if assignment.shared_deadline
            else now
        )
        deadline = anchor + dt.timedelta(minutes=assignment.duration_minutes)
        attempt = Attempt(
            student_id=student.id,
            assignment_id=assignment_id,
            session_token=session_token,
            shuffle_seed=shuffle_seed,
            started_at=now,
            deadline_at=deadline,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        questions = _get_shuffled_questions(assignment, shuffle_seed, db)
        return AttemptStart(
            attempt_id=attempt.id,
            session_token=session_token,
            questions=questions,
            duration_minutes=assignment.duration_minutes,
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


@router.post("/api/attempts/{attempt_id}/heartbeat", response_model=HeartbeatResponse)
def heartbeat_attempt(
    attempt_id: int,
    body: HeartbeatRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    x_session_token: str | None = Header(None),
):
    """Re-anchor the client clock + optionally upsert answers in one round-trip.

    Called every ~30s and on visibility/online events. Server is the only
    authority for `deadline_at`; if the attempt has already expired this auto-
    grades it and reports back. The client must not extend its local timer
    based on anything other than the (server_now, deadline_at) pair returned
    here.
    """
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    _verify_session_token(attempt, x_session_token)

    now = _utcnow()

    if attempt.submitted_at is not None:
        return HeartbeatResponse(
            server_now=now,
            deadline_at=_attempt_deadline(attempt),
            status="submitted",
            expired=False,
            score=attempt.score,
        )

    if _is_attempt_expired(attempt, now):
        _auto_grade_expired(attempt, db, now=now)
        db.refresh(attempt)
        return HeartbeatResponse(
            server_now=now,
            deadline_at=_attempt_deadline(attempt),
            status="expired",
            expired=True,
            score=attempt.score,
        )

    if body.answers is not None:
        _upsert_answers(attempt, body.answers, db, grade=False)

    return HeartbeatResponse(
        server_now=now,
        deadline_at=_attempt_deadline(attempt),
        status="in_progress",
        expired=False,
        score=None,
    )


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

    # Defensive guard against duplicate attempts created by concurrent start calls.
    submitted_sibling = (
        db.query(Attempt)
        .filter(
            Attempt.assignment_id == attempt.assignment_id,
            Attempt.student_id == attempt.student_id,
            Attempt.id != attempt.id,
            Attempt.submitted_at.is_not(None),
        )
        .first()
    )
    if submitted_sibling is not None:
        db.delete(attempt)
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Already submitted")

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
    duplicate_unfinished = (
        db.query(Attempt)
        .filter(
            Attempt.assignment_id == attempt.assignment_id,
            Attempt.student_id == attempt.student_id,
            Attempt.id != attempt.id,
            Attempt.submitted_at.is_(None),
        )
        .all()
    )
    for dup in duplicate_unfinished:
        db.delete(dup)
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
    view_mode = _student_view_mode(assignment)
    if view_mode == "closed":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Results not released yet")
    if view_mode == "attempt" and not attempt.submitted_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Attempt is not submitted yet")

    quiz = assignment.quiz
    max_score = sum(q.points for q in quiz.questions)
    answers_map = {a.question_id: a for a in attempt.answers}

    question_details = []
    for q in quiz.questions:
        ans = answers_map.get(q.id)
        if view_mode == "attempt":
            question_details.append(ResultQuestionDetail(
                question_id=q.id,
                title=q.title,
                q_type=q.q_type,
                points=q.points,
                points_awarded=0,
                is_correct=None,
                selected_option_ids=ans.selected_option_ids if ans else None,
                text_answer=ans.text_answer if ans else None,
                correct_option_ids=None,
                accepted_answers=None,
                explanation_md=None,
                options=[
                    OptionOutTeacher(
                        id=o.id,
                        order_index=o.order_index,
                        text_md=o.text_md,
                        is_correct=False,
                    )
                    for o in q.options
                ],
                body_md=q.body_md,
            ))
        else:
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
        score=attempt.score if view_mode == "results" else None,
        max_score=max_score if view_mode == "results" else 0,
        student_view_mode=view_mode,
        submitted_at=attempt.submitted_at,
        questions=question_details,
    )
