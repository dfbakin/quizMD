"""Tests for the background sweep task that auto-grades expired attempts."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.main import sweep_expired_attempts_once
from app.models import Attempt
from tests.conftest import (
    create_test_teacher,
    create_test_group,
    create_test_student,
    create_test_quiz,
    create_test_assignment,
)


def _utcnow_naive() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class _NonClosingSession:
    """Wraps a Session so the sweep's `.close()` is a no-op (the test fixture
    owns the session lifecycle)."""

    def __init__(self, session: Session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):  # noqa: D401 — no-op
        pass


def _make_attempt(
    db: Session,
    *,
    student_id: int,
    assignment_id: int,
    started: dt.datetime,
    deadline: dt.datetime,
    suffix: str,
) -> Attempt:
    att = Attempt(
        student_id=student_id,
        assignment_id=assignment_id,
        session_token=f"sweep-tok-{suffix}",
        shuffle_seed=f"sweep-seed-{suffix}",
        started_at=started,
        deadline_at=deadline,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


class TestSweepExpiredAttempts:
    def test_grades_expired_unsubmitted_attempts(self, db: Session):
        teacher = create_test_teacher(db)
        group = create_test_group(db, teacher.id)
        student = create_test_student(db, group.id)
        quiz = create_test_quiz(db, teacher.id)
        assignment = create_test_assignment(db, quiz.id, group.id)

        now = _utcnow_naive()
        att = _make_attempt(
            db,
            student_id=student.id,
            assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=20),
            deadline=now - dt.timedelta(minutes=5),
            suffix="expired",
        )
        att_id = att.id

        graded = sweep_expired_attempts_once(
            db_factory=lambda: _NonClosingSession(db), now=now
        )
        assert graded == 1

        db.expire_all()
        att = db.get(Attempt, att_id)
        assert att.submitted_at is not None
        # submitted_at is clamped to the snapshot deadline, not "now".
        assert att.submitted_at == now - dt.timedelta(minutes=5)
        assert att.score is not None

    def test_skips_in_progress_attempts(self, db: Session):
        teacher = create_test_teacher(db)
        group = create_test_group(db, teacher.id)
        student = create_test_student(db, group.id)
        quiz = create_test_quiz(db, teacher.id)
        assignment = create_test_assignment(db, quiz.id, group.id)

        now = _utcnow_naive()
        att = _make_attempt(
            db,
            student_id=student.id,
            assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=2),
            deadline=now + dt.timedelta(minutes=10),
            suffix="active",
        )
        att_id = att.id

        graded = sweep_expired_attempts_once(
            db_factory=lambda: _NonClosingSession(db), now=now
        )
        assert graded == 0

        db.expire_all()
        att = db.get(Attempt, att_id)
        assert att.submitted_at is None

    def test_skips_already_submitted_attempts(self, db: Session):
        teacher = create_test_teacher(db)
        group = create_test_group(db, teacher.id)
        student = create_test_student(db, group.id)
        quiz = create_test_quiz(db, teacher.id)
        assignment = create_test_assignment(db, quiz.id, group.id)

        now = _utcnow_naive()
        already = _make_attempt(
            db,
            student_id=student.id,
            assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=20),
            deadline=now - dt.timedelta(minutes=5),
            suffix="already-submitted",
        )
        already.submitted_at = now - dt.timedelta(minutes=4)
        already.score = 7
        db.commit()

        graded = sweep_expired_attempts_once(
            db_factory=lambda: _NonClosingSession(db), now=now
        )
        assert graded == 0

    def test_handles_mixed_batch(self, db: Session):
        teacher = create_test_teacher(db)
        group = create_test_group(db, teacher.id)
        s1 = create_test_student(db, group.id, username="sweep-s1")
        s2 = create_test_student(db, group.id, username="sweep-s2")
        s3 = create_test_student(db, group.id, username="sweep-s3")
        quiz = create_test_quiz(db, teacher.id)
        assignment = create_test_assignment(db, quiz.id, group.id)

        now = _utcnow_naive()
        # Two expired, one active.
        _make_attempt(
            db, student_id=s1.id, assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=20),
            deadline=now - dt.timedelta(minutes=5),
            suffix="exp1",
        )
        _make_attempt(
            db, student_id=s2.id, assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=15),
            deadline=now - dt.timedelta(minutes=1),
            suffix="exp2",
        )
        _make_attempt(
            db, student_id=s3.id, assignment_id=assignment.id,
            started=now - dt.timedelta(minutes=2),
            deadline=now + dt.timedelta(minutes=10),
            suffix="active",
        )

        graded = sweep_expired_attempts_once(
            db_factory=lambda: _NonClosingSession(db), now=now
        )
        assert graded == 2
