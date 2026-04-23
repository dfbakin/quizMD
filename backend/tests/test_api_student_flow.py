"""Integration tests for the full student quiz-taking flow:
start -> save -> submit -> verify score -> view results.
"""

import io
import datetime as dt
import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher, create_test_group, create_test_student, SAMPLE_QUIZ_MD
from app.models import Attempt, Assignment


def _setup_full(app_client, db: Session):
    """Set up teacher, group, student, quiz, assignment. Returns headers and IDs."""
    create_test_teacher(db, "teach", "pass")
    t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
    app_client.post(
        f"/api/groups/{group['id']}/students",
        json={"students": [{"username": "s1", "password": "pass", "display_name": "Student 1"}]},
        headers=t_headers,
    )

    file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
    quiz = app_client.post(
        "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=t_headers,
    ).json()

    now = dt.datetime.now(dt.timezone.utc)
    assignment = app_client.post("/api/assignments", json={
        "quiz_id": quiz["id"],
        "group_id": group["id"],
        "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
        "duration_minutes": 65,
    }, headers=t_headers).json()

    s_login = app_client.post("/api/auth/login", json={"username": "s1", "password": "pass"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    return t_headers, s_headers, quiz, assignment


class TestStudentAssignmentList:
    def test_list_active(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        resp = app_client.get("/api/my/assignments", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "active"
        assert data[0]["attempt_id"] is None


class TestStartAttempt:
    def test_start_success(self, db: Session, app_client):
        _, s_headers, quiz, assignment = _setup_full(app_client, db)
        resp = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "attempt_id" in data
        assert "session_token" in data
        assert len(data["questions"]) == 3

    def test_start_returns_same_attempt_with_rotated_token(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        r1 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        r2 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        assert r1["attempt_id"] == r2["attempt_id"]
        assert r1["session_token"] != r2["session_token"]

    def test_questions_have_no_correct_answers(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        data = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        for q in data["questions"]:
            for o in q["options"]:
                assert "is_correct" not in o


class TestSaveAnswers:
    def test_save(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        resp = app_client.post(f"/api/attempts/{attempt_id}/save", json={
            "answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}],
        }, headers={**s_headers, "X-Session-Token": token})
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"


class TestSubmitAndGrade:
    def test_submit_all_correct(self, db: Session, app_client):
        t_headers, s_headers, quiz, assignment = _setup_full(app_client, db)

        quiz_detail = app_client.get(f"/api/quizzes/{quiz['id']}", headers=t_headers).json()

        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        sh = {**s_headers, "X-Session-Token": token}

        answers = []
        for sq in start["questions"]:
            teacher_q = next(tq for tq in quiz_detail["questions"] if tq["id"] == sq["id"])
            if teacher_q["q_type"] in ("single", "multiple"):
                correct_ids = [o["id"] for o in teacher_q["options"] if o["is_correct"]]
                answers.append({"question_id": sq["id"], "selected_option_ids": correct_ids})
            else:
                answers.append({"question_id": sq["id"], "text_answer": teacher_q["accepted_answers"][0]})

        resp = app_client.post(f"/api/attempts/{attempt_id}/submit", json={"answers": answers}, headers=sh)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["score"] == 3

    def test_submit_all_wrong(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        sh = {**s_headers, "X-Session-Token": start["session_token"]}

        answers = []
        for q in start["questions"]:
            if q["q_type"] in ("single", "multiple"):
                wrong_id = q["options"][-1]["id"]
                answers.append({"question_id": q["id"], "selected_option_ids": [wrong_id]})
            else:
                answers.append({"question_id": q["id"], "text_answer": "wrong"})

        resp = app_client.post(f"/api/attempts/{attempt_id}/submit", json={"answers": answers}, headers=sh)
        assert resp.status_code == 200
        assert resp.json()["score"] == 0

    def test_double_submit_rejected(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        sh = {**s_headers, "X-Session-Token": start["session_token"]}

        app_client.post(f"/api/attempts/{attempt_id}/submit", json={"answers": []}, headers=sh)
        resp = app_client.post(f"/api/attempts/{attempt_id}/submit", json={"answers": []}, headers=sh)
        assert resp.status_code == 409


class TestResults:
    def test_results_hidden_by_default(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        app_client.post(f"/api/attempts/{start['attempt_id']}/submit", json={"answers": []}, headers=sh)

        resp = app_client.get(f"/api/attempts/{start['attempt_id']}/results", headers=s_headers)
        assert resp.status_code == 403

    def test_results_visible_after_toggle(self, db: Session, app_client):
        t_headers, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        app_client.post(f"/api/attempts/{start['attempt_id']}/submit", json={"answers": []}, headers=sh)

        app_client.patch(
            f"/api/assignments/{assignment['id']}",
            json={"results_visible": True},
            headers=t_headers,
        )

        resp = app_client.get(f"/api/attempts/{start['attempt_id']}/results", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_score"] == 3
        assert data["questions"][0]["explanation_md"] is not None

    def test_teacher_sees_results(self, db: Session, app_client):
        t_headers, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        app_client.post(f"/api/attempts/{start['attempt_id']}/submit", json={"answers": []}, headers=sh)

        resp = app_client.get(f"/api/assignments/{assignment['id']}/results", headers=t_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["quiz_title"] == "Тестовый квиз"
        assert len(data["results"]) == 1

    def test_attempt_view_only_for_submitted_attempts(self, db: Session, app_client):
        t_headers, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        app_client.patch(
            f"/api/assignments/{assignment['id']}",
            json={"student_view_mode": "attempt"},
            headers=t_headers,
        )

        resp = app_client.get(f"/api/attempts/{start['attempt_id']}/results", headers=s_headers)
        assert resp.status_code == 403

    def test_attempt_view_shows_submitted_answers_without_correctness(self, db: Session, app_client):
        t_headers, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        first_q = start["questions"][0]
        first_opt = first_q["options"][0]["id"]

        app_client.post(
            f"/api/attempts/{start['attempt_id']}/submit",
            json={"answers": [{"question_id": first_q["id"], "selected_option_ids": [first_opt]}]},
            headers=sh,
        )
        app_client.patch(
            f"/api/assignments/{assignment['id']}",
            json={"student_view_mode": "attempt"},
            headers=t_headers,
        )

        resp = app_client.get(f"/api/attempts/{start['attempt_id']}/results", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_view_mode"] == "attempt"
        assert data["score"] is None
        assert data["max_score"] == 0
        q0 = data["questions"][0]
        assert q0["selected_option_ids"] == [first_opt]
        assert q0["is_correct"] is None
        assert q0["correct_option_ids"] is None
        assert q0["accepted_answers"] is None
        assert q0["explanation_md"] is None


class TestDuplicateAttemptHandling:
    def test_list_prefers_submitted_attempt_when_duplicates_exist(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        submitted = db.get(Attempt, start["attempt_id"])
        assert submitted is not None
        submitted.submitted_at = dt.datetime.now(dt.timezone.utc)
        submitted.score = 1
        db.add(Attempt(
            student_id=submitted.student_id,
            assignment_id=submitted.assignment_id,
            session_token=f"dup-token-{submitted.id}",
            shuffle_seed=f"dup-seed-{submitted.id}",
            started_at=submitted.started_at,
            deadline_at=submitted.deadline_at,
        ))
        db.commit()

        resp = app_client.get("/api/my/assignments", headers=s_headers)
        assert resp.status_code == 200
        row = resp.json()[0]
        assert row["status"] == "completed"
        assert row["attempt_id"] == submitted.id

    def test_reentry_deduplicates_open_attempts_and_single_submit_finishes(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        primary = db.get(Attempt, start["attempt_id"])
        assert primary is not None
        db.add(Attempt(
            student_id=primary.student_id,
            assignment_id=primary.assignment_id,
            session_token=f"dup-token-open-{primary.id}",
            shuffle_seed=f"dup-seed-open-{primary.id}",
            started_at=primary.started_at,
            deadline_at=primary.deadline_at,
        ))
        db.commit()

        reentry = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers)
        assert reentry.status_code == 200
        reentry_data = reentry.json()
        sh = {**s_headers, "X-Session-Token": reentry_data["session_token"]}

        attempts_after_reentry = (
            db.query(Attempt)
            .filter(
                Attempt.assignment_id == assignment["id"],
                Attempt.student_id == primary.student_id,
            )
            .all()
        )
        assert len(attempts_after_reentry) == 1

        submit = app_client.post(
            f"/api/attempts/{reentry_data['attempt_id']}/submit",
            json={"answers": []},
            headers=sh,
        )
        assert submit.status_code == 200

        start_again = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers)
        assert start_again.status_code == 409

        list_resp = app_client.get("/api/my/assignments", headers=s_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()[0]["status"] == "completed"

    def test_submit_on_stale_duplicate_is_rejected_and_cleaned(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        first_submit = app_client.post(
            f"/api/attempts/{start['attempt_id']}/submit",
            json={"answers": []},
            headers=sh,
        )
        assert first_submit.status_code == 200

        submitted = db.get(Attempt, start["attempt_id"])
        assert submitted is not None
        dup = Attempt(
            student_id=submitted.student_id,
            assignment_id=submitted.assignment_id,
            session_token=f"dup-token-stale-{submitted.id}",
            shuffle_seed=f"dup-seed-stale-{submitted.id}",
            started_at=submitted.started_at,
            deadline_at=submitted.deadline_at,
        )
        db.add(dup)
        db.commit()
        db.refresh(dup)

        stale_submit = app_client.post(
            f"/api/attempts/{dup.id}/submit",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": dup.session_token},
        )
        assert stale_submit.status_code == 409

        remaining = (
            db.query(Attempt)
            .filter(
                Attempt.assignment_id == assignment["id"],
                Attempt.student_id == submitted.student_id,
            )
            .all()
        )
        assert len(remaining) == 1
        assert remaining[0].id == submitted.id
        assert remaining[0].submitted_at is not None


class TestDeadlineEnforcement:
    def test_save_rejected_when_attempt_deadline_passed(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        # Move the per-attempt snapshot deadline into the past.
        attempt = db.get(Attempt, attempt_id)
        assert attempt is not None
        attempt.deadline_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 409

    def test_save_still_works_when_assignment_window_closed_but_attempt_deadline_in_future(
        self, db: Session, app_client
    ):
        """Attempt deadlines are snapshotted at start; subsequent edits to the
        parent Assignment must NOT shorten an in-flight attempt."""
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        ass = db.get(Assignment, assignment["id"])
        assert ass is not None
        ass.ends_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 200

    def test_submit_rejected_when_attempt_deadline_passed_and_auto_grades(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        attempt = db.get(Attempt, attempt_id)
        assert attempt is not None
        deadline_in_past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        attempt.deadline_at = deadline_in_past
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 409

        db.refresh(attempt)
        assert attempt.submitted_at is not None
        assert attempt.submitted_at.replace(tzinfo=None) == deadline_in_past.replace(tzinfo=None)


class TestAttemptDeadlineSnapshot:
    def test_deadline_at_is_started_at_plus_duration(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()

        started_at = dt.datetime.fromisoformat(start["started_at"].replace("Z", "+00:00"))
        deadline_at = dt.datetime.fromisoformat(start["deadline_at"].replace("Z", "+00:00"))
        assert (deadline_at - started_at) == dt.timedelta(minutes=assignment["duration_minutes"])

    def test_deadline_immune_to_assignment_duration_change(self, db: Session, app_client):
        t_headers, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        original_deadline = dt.datetime.fromisoformat(start["deadline_at"].replace("Z", "+00:00"))

        # Halve the assignment duration AFTER the attempt snapshot was taken.
        new_duration = max(1, assignment["duration_minutes"] // 2)
        patch = app_client.patch(
            f"/api/assignments/{assignment['id']}",
            json={"duration_minutes": new_duration},
            headers=t_headers,
        )
        assert patch.status_code == 200

        att = db.get(Attempt, start["attempt_id"])
        assert att is not None
        assert att.deadline_at.replace(tzinfo=None) == original_deadline.replace(tzinfo=None)


class TestStartWindowDecoupledFromDuration:
    """Crucial regression coverage for the new split: start_window_minutes
    governs only when the *Start* button is allowed; once the attempt has
    started, the per-attempt deadline_at uses duration_minutes regardless of
    where in the start window the student happened to begin."""

    def _setup(self, app_client, db: Session, *, start_window: int, duration: int, starts_at: dt.datetime):
        create_test_teacher(db, "teach", "pass")
        t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
        app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1"}]},
            headers=t_headers,
        )

        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        quiz = app_client.post(
            "/api/quizzes/import",
            files={"file": ("q.md", file, "text/markdown")},
            headers=t_headers,
        ).json()

        assignment = app_client.post("/api/assignments", json={
            "quiz_id": quiz["id"],
            "group_id": group["id"],
            "starts_at": starts_at.isoformat(),
            "start_window_minutes": start_window,
            "duration_minutes": duration,
        }, headers=t_headers).json()

        s_login = app_client.post("/api/auth/login", json={"username": "s1", "password": "pass"})
        s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}
        return t_headers, s_headers, assignment

    def test_late_start_inside_window_still_grants_full_duration(self, db: Session, app_client):
        """The whole point of decoupling: a student who starts 50 minutes into
        a 60-minute start window still gets the full per-attempt clock (e.g.
        30 min) — their personal deadline can fall *after* the assignment's
        start window closed."""
        now = dt.datetime.now(dt.timezone.utc)
        # 60-min start window, 30-min attempt clock. Assignment opened 50 min ago.
        starts_at = now - dt.timedelta(minutes=50)
        _, s_headers, assignment = self._setup(
            app_client, db, start_window=60, duration=30, starts_at=starts_at,
        )

        resp = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers)
        assert resp.status_code == 200
        data = resp.json()

        started_at = dt.datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
        deadline_at = dt.datetime.fromisoformat(data["deadline_at"].replace("Z", "+00:00"))
        # The per-attempt clock honours duration_minutes, NOT the remaining
        # start window. Students who join late are not penalized.
        assert deadline_at - started_at == dt.timedelta(minutes=30)

        # And that personal deadline can fall after the assignment-level
        # ends_at — which only governs the start gate.
        assignment_ends_at = dt.datetime.fromisoformat(
            assignment["ends_at"].replace("Z", "+00:00")
        )
        assert deadline_at > assignment_ends_at

    def test_start_after_window_close_is_rejected(self, db: Session, app_client):
        now = dt.datetime.now(dt.timezone.utc)
        # 5-min start window, opened 10 min ago — start window has closed.
        starts_at = now - dt.timedelta(minutes=10)
        _, s_headers, assignment = self._setup(
            app_client, db, start_window=5, duration=30, starts_at=starts_at,
        )

        resp = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers)
        assert resp.status_code == 403
        assert "deadline" in resp.json()["detail"].lower() or "passed" in resp.json()["detail"].lower()

    def test_my_assignments_exposes_both_windows(self, db: Session, app_client):
        now = dt.datetime.now(dt.timezone.utc)
        starts_at = now - dt.timedelta(minutes=1)
        _, s_headers, assignment = self._setup(
            app_client, db, start_window=120, duration=30, starts_at=starts_at,
        )

        listing = app_client.get("/api/my/assignments", headers=s_headers).json()
        assert len(listing) == 1
        a = listing[0]
        assert a["start_window_minutes"] == 120
        assert a["duration_minutes"] == 30
        # ends_at on the listing reflects the start window, not the per-attempt clock.
        starts = dt.datetime.fromisoformat(a["starts_at"].replace("Z", "+00:00"))
        ends = dt.datetime.fromisoformat(a["ends_at"].replace("Z", "+00:00"))
        assert ends - starts == dt.timedelta(minutes=120)


class TestSharedDeadlineMode:
    """Shared-deadline mode anchors every Attempt's ``deadline_at`` to
    ``starts_at + duration_minutes`` instead of ``started_at + duration_minutes``.
    Late starters get less time on the clock — the trade-off the teacher
    explicitly opted into when flipping the switch."""

    def _setup_assignment(
        self,
        app_client,
        db: Session,
        *,
        starts_at: dt.datetime,
        duration: int,
        students: list[str],
        shared_deadline: bool,
    ):
        create_test_teacher(db, "teach", "pass")
        t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
        app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [
                {"username": u, "password": "pass", "display_name": u.upper()}
                for u in students
            ]},
            headers=t_headers,
        )

        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        quiz = app_client.post(
            "/api/quizzes/import",
            files={"file": ("q.md", file, "text/markdown")},
            headers=t_headers,
        ).json()

        assignment = app_client.post("/api/assignments", json={
            "quiz_id": quiz["id"],
            "group_id": group["id"],
            "starts_at": starts_at.isoformat(),
            "duration_minutes": duration,
            "shared_deadline": shared_deadline,
        }, headers=t_headers).json()

        student_headers: list[dict] = []
        for u in students:
            login = app_client.post("/api/auth/login", json={"username": u, "password": "pass"}).json()
            student_headers.append({"Authorization": f"Bearer {login['access_token']}"})
        return t_headers, student_headers, assignment

    def test_shared_deadline_anchors_to_starts_at_for_every_student(self, db: Session, app_client):
        """Two students starting at different moments share an identical
        ``deadline_at`` (== starts_at + duration). The deadline is a property
        of the assignment, not the individual attempt."""
        starts_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        _, [alice, bob], assignment = self._setup_assignment(
            app_client, db,
            starts_at=starts_at, duration=30, students=["alice", "bob"],
            shared_deadline=True,
        )

        a_start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=alice).json()
        b_start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=bob).json()

        a_deadline = dt.datetime.fromisoformat(a_start["deadline_at"].replace("Z", "+00:00"))
        b_deadline = dt.datetime.fromisoformat(b_start["deadline_at"].replace("Z", "+00:00"))
        assert a_deadline == b_deadline

        starts = dt.datetime.fromisoformat(assignment["starts_at"].replace("Z", "+00:00"))
        assert a_deadline.replace(tzinfo=None) == (starts + dt.timedelta(minutes=30)).replace(tzinfo=None)

    def test_shared_deadline_means_late_start_gets_less_time(self, db: Session, app_client):
        """Bob, starting 10 min into a 30-min shared-deadline quiz, has only
        ~20 min on the clock — the deadline is fixed at starts_at+30."""
        starts_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)
        _, [bob], assignment = self._setup_assignment(
            app_client, db,
            starts_at=starts_at, duration=30, students=["bob"],
            shared_deadline=True,
        )

        b_start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=bob).json()
        started_at = dt.datetime.fromisoformat(b_start["started_at"].replace("Z", "+00:00"))
        deadline_at = dt.datetime.fromisoformat(b_start["deadline_at"].replace("Z", "+00:00"))
        remaining = deadline_at - started_at
        # The full 30 min minus the ~10 min Bob delayed (allow a small fudge for test runtime).
        assert dt.timedelta(minutes=19) < remaining < dt.timedelta(minutes=21), remaining

    def test_per_student_mode_unchanged_late_start_gets_full_clock(self, db: Session, app_client):
        """Sanity guard: with shared_deadline=False (the default) the late
        starter still gets the full per-attempt window."""
        starts_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)
        _, [bob], assignment = self._setup_assignment(
            app_client, db,
            starts_at=starts_at, duration=30, students=["bob"],
            shared_deadline=False,
        )

        b_start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=bob).json()
        started_at = dt.datetime.fromisoformat(b_start["started_at"].replace("Z", "+00:00"))
        deadline_at = dt.datetime.fromisoformat(b_start["deadline_at"].replace("Z", "+00:00"))
        assert deadline_at - started_at == dt.timedelta(minutes=30)

    def test_creating_with_shared_deadline_forces_start_window_to_duration(self, db: Session, app_client):
        """Default helper does not pass start_window_minutes, but the server
        still pins it to duration_minutes in shared mode."""
        starts_at = dt.datetime.now(dt.timezone.utc)
        _, _, assignment = self._setup_assignment(
            app_client, db,
            starts_at=starts_at, duration=30, students=["alice"],
            shared_deadline=True,
        )
        assert assignment["shared_deadline"] is True
        assert assignment["start_window_minutes"] == 30
        assert assignment["duration_minutes"] == 30

    def test_create_with_shared_and_overridden_start_window_is_pinned(self, db: Session, app_client):
        """Caller-supplied start_window_minutes is silently overridden in
        shared mode — the UI hides the field for the same reason."""
        create_test_teacher(db, "teach", "pass")
        t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        quiz = app_client.post(
            "/api/quizzes/import",
            files={"file": ("q.md", file, "text/markdown")},
            headers=t_headers,
        ).json()

        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz["id"],
            "group_id": group["id"],
            "starts_at": now.isoformat(),
            "start_window_minutes": 120,
            "duration_minutes": 30,
            "shared_deadline": True,
        }, headers=t_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["start_window_minutes"] == 30

    def test_switching_to_shared_mode_repins_start_window(self, db: Session, app_client):
        """Flipping an existing assignment to shared mode must repin
        ``start_window_minutes`` (and recompute ``ends_at``)."""
        create_test_teacher(db, "teach", "pass")
        t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        quiz = app_client.post(
            "/api/quizzes/import",
            files={"file": ("q.md", file, "text/markdown")},
            headers=t_headers,
        ).json()

        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz["id"],
            "group_id": group["id"],
            "starts_at": now.isoformat(),
            "start_window_minutes": 120,
            "duration_minutes": 30,
        }, headers=t_headers).json()
        assert created["shared_deadline"] is False
        assert created["start_window_minutes"] == 120

        patched = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"shared_deadline": True},
            headers=t_headers,
        ).json()
        assert patched["shared_deadline"] is True
        assert patched["start_window_minutes"] == 30
        starts = dt.datetime.fromisoformat(patched["starts_at"].replace("Z", "+00:00"))
        ends = dt.datetime.fromisoformat(patched["ends_at"].replace("Z", "+00:00"))
        assert ends - starts == dt.timedelta(minutes=30)

    def test_switching_off_shared_mode_leaves_window_alone(self, db: Session, app_client):
        """Switching shared mode OFF does not re-expand the start window;
        the teacher widens it explicitly afterwards if they want."""
        create_test_teacher(db, "teach", "pass")
        t_login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        group = app_client.post("/api/groups", json={"name": "11А"}, headers=t_headers).json()
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        quiz = app_client.post(
            "/api/quizzes/import",
            files={"file": ("q.md", file, "text/markdown")},
            headers=t_headers,
        ).json()

        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz["id"],
            "group_id": group["id"],
            "starts_at": now.isoformat(),
            "duration_minutes": 30,
            "shared_deadline": True,
        }, headers=t_headers).json()
        assert created["start_window_minutes"] == 30

        patched = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"shared_deadline": False},
            headers=t_headers,
        ).json()
        assert patched["shared_deadline"] is False
        assert patched["start_window_minutes"] == 30

    def test_in_progress_attempt_immune_to_shared_mode_flip(self, db: Session, app_client):
        """An attempt snapshotted with the per-student rule keeps its
        ``deadline_at`` when the teacher later flips shared mode on, by the
        same immutability guarantee that protects it from duration edits."""
        starts_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        t_headers, [alice], assignment = self._setup_assignment(
            app_client, db,
            starts_at=starts_at, duration=30, students=["alice"],
            shared_deadline=False,
        )

        a_start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=alice).json()
        original_deadline = dt.datetime.fromisoformat(a_start["deadline_at"].replace("Z", "+00:00"))

        app_client.patch(
            f"/api/assignments/{assignment['id']}",
            json={"shared_deadline": True},
            headers=t_headers,
        )

        att = db.get(Attempt, a_start["attempt_id"])
        assert att is not None
        assert att.deadline_at.replace(tzinfo=None) == original_deadline.replace(tzinfo=None)


class TestHeartbeat:
    def _start(self, app_client, s_headers, assignment_id: int) -> dict:
        return app_client.post(f"/api/assignments/{assignment_id}/start", headers=s_headers).json()

    def test_heartbeat_returns_server_now_and_deadline(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = self._start(app_client, s_headers, assignment["id"])
        sh = {**s_headers, "X-Session-Token": start["session_token"]}

        resp = app_client.post(
            f"/api/attempts/{start['attempt_id']}/heartbeat",
            json={},
            headers=sh,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["expired"] is False
        assert data["deadline_at"] == start["deadline_at"]
        assert data["server_now"].endswith("Z")

    def test_heartbeat_persists_answers_and_does_not_grade(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = self._start(app_client, s_headers, assignment["id"])
        sh = {**s_headers, "X-Session-Token": start["session_token"]}
        q = start["questions"][0]

        resp = app_client.post(
            f"/api/attempts/{start['attempt_id']}/heartbeat",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers=sh,
        )
        assert resp.status_code == 200
        att = db.get(Attempt, start["attempt_id"])
        assert att is not None
        assert len(att.answers) == 1
        # Heartbeat does NOT grade, only persists.
        assert att.answers[0].is_correct is None
        assert att.answers[0].points_awarded == 0

    def test_heartbeat_after_deadline_auto_grades_and_returns_expired(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = self._start(app_client, s_headers, assignment["id"])
        sh = {**s_headers, "X-Session-Token": start["session_token"]}

        att = db.get(Attempt, start["attempt_id"])
        assert att is not None
        att.deadline_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{start['attempt_id']}/heartbeat",
            json={},
            headers=sh,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "expired"
        assert data["expired"] is True

        db.refresh(att)
        assert att.submitted_at is not None

    def test_heartbeat_with_wrong_token_rejected(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = self._start(app_client, s_headers, assignment["id"])
        resp = app_client.post(
            f"/api/attempts/{start['attempt_id']}/heartbeat",
            json={},
            headers={**s_headers, "X-Session-Token": "wrong"},
        )
        assert resp.status_code == 403
