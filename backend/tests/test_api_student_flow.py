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
    def test_save_rejected_when_attempt_time_limit_expired(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        attempt = db.get(Attempt, attempt_id)
        assert attempt is not None
        attempt.started_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30)
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 409

    def test_save_rejected_when_assignment_window_is_closed(self, db: Session, app_client):
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
        assert resp.status_code == 409

    def test_submit_rejected_by_earlier_assignment_end_deadline(self, db: Session, app_client):
        _, s_headers, _, assignment = _setup_full(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]
        q = start["questions"][0]

        attempt = db.get(Attempt, attempt_id)
        assert attempt is not None
        attempt.started_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        ass = db.get(Assignment, assignment["id"])
        assert ass is not None
        ass.ends_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        db.commit()

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 409

        db.refresh(attempt)
        assert attempt.submitted_at is not None
        assert attempt.submitted_at.replace(tzinfo=None) == ass.ends_at.replace(tzinfo=None)
