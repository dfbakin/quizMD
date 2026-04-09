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
