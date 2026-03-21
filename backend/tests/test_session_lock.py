"""Tests for one-session lock: second session must be rejected."""

import io
import datetime as dt
import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher, create_test_group, create_test_student, SAMPLE_QUIZ_MD


def _setup(app_client, db: Session):
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
    quiz = app_client.post("/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=t_headers).json()

    now = dt.datetime.now(dt.timezone.utc)
    assignment = app_client.post("/api/assignments", json={
        "quiz_id": quiz["id"], "group_id": group["id"],
        "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
        "duration_minutes": 65,
    }, headers=t_headers).json()

    s_login = app_client.post("/api/auth/login", json={"username": "s1", "password": "pass"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    return s_headers, assignment


class TestSessionLock:
    def test_save_with_wrong_token_rejected(self, db: Session, app_client):
        s_headers, assignment = _setup(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_submit_with_wrong_token_rejected(self, db: Session, app_client):
        s_headers, assignment = _setup(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_save_with_correct_token_succeeds(self, db: Session, app_client):
        s_headers, assignment = _setup(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert resp.status_code == 200

    def test_save_without_token_rejected(self, db: Session, app_client):
        """When no X-Session-Token header is sent, should be rejected."""
        s_headers, assignment = _setup(app_client, db)
        start = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]

        resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers=s_headers,
        )
        assert resp.status_code == 403

    def test_token_rotates_on_reentry(self, db: Session, app_client):
        """Second start call should return a new token, invalidating the old one."""
        s_headers, assignment = _setup(app_client, db)
        start1 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        token1 = start1["session_token"]

        start2 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        token2 = start2["session_token"]

        assert token1 != token2
        assert start1["attempt_id"] == start2["attempt_id"]

        resp = app_client.post(
            f"/api/attempts/{start1['attempt_id']}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token1},
        )
        assert resp.status_code == 403

        resp = app_client.post(
            f"/api/attempts/{start1['attempt_id']}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token2},
        )
        assert resp.status_code == 200

    def test_saved_answers_restored_on_reentry(self, db: Session, app_client):
        """Answers saved before should be returned on re-entry."""
        s_headers, assignment = _setup(app_client, db)
        start1 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        token1 = start1["session_token"]
        q = start1["questions"][0]

        app_client.post(
            f"/api/attempts/{start1['attempt_id']}/save",
            json={"answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}]},
            headers={**s_headers, "X-Session-Token": token1},
        )

        start2 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        saved = start2["saved_answers"]
        assert len(saved) == 1
        assert saved[0]["question_id"] == q["id"]
        assert saved[0]["selected_option_ids"] == [q["options"][0]["id"]]

    def test_questions_same_order_on_reentry(self, db: Session, app_client):
        """Question order must be identical across re-entries."""
        s_headers, assignment = _setup(app_client, db)
        start1 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()
        start2 = app_client.post(f"/api/assignments/{assignment['id']}/start", headers=s_headers).json()

        ids1 = [q["id"] for q in start1["questions"]]
        ids2 = [q["id"] for q in start2["questions"]]
        assert ids1 == ids2
