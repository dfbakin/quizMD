"""Tests for assignment CRUD API."""

import csv
import io
import datetime as dt
import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher, SAMPLE_QUIZ_MD


def _setup(app_client, db: Session):
    """Create teacher, group, quiz, return headers + ids."""
    create_test_teacher(db, "teach", "pass")
    login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    group = app_client.post("/api/groups", json={"name": "11А"}, headers=headers).json()
    file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
    quiz = app_client.post(
        "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers,
    ).json()
    return headers, quiz["id"], group["id"]


def _parse_utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


class TestAssignmentCRUD:
    def test_create_assignment(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id,
            "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "duration_minutes": 60,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["quiz_title"] == "Тестовый квиз"
        assert data["group_name"] == "11А"
        assert data["duration_minutes"] == 60
        assert data["time_limit_minutes"] == 10
        assert data["student_view_mode"] == "closed"
        assert "share_code" in data

    def test_list_assignments(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 45,
        }, headers=headers)
        resp = app_client.get("/api/assignments", headers=headers)
        assert len(resp.json()) == 1

    def test_toggle_results_visible(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 60,
        }, headers=headers).json()
        assert created["results_visible"] is False

        resp = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"results_visible": True},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["results_visible"] is True
        assert resp.json()["student_view_mode"] == "results"

    def test_change_student_view_mode(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 60,
        }, headers=headers).json()
        assert created["student_view_mode"] == "closed"

        attempt_mode = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"student_view_mode": "attempt"},
            headers=headers,
        )
        assert attempt_mode.status_code == 200
        assert attempt_mode.json()["student_view_mode"] == "attempt"
        assert attempt_mode.json()["results_visible"] is False

        results_mode = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"student_view_mode": "results"},
            headers=headers,
        )
        assert results_mode.status_code == 200
        assert results_mode.json()["student_view_mode"] == "results"
        assert results_mode.json()["results_visible"] is True

    def test_share_code_lookup(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()
        code = created["share_code"]

        resp = app_client.get(f"/api/assignments/by-code/{code}")
        assert resp.status_code == 200
        assert resp.json()["assignment_id"] == created["id"]
        assert resp.json()["quiz_title"] == "Тестовый квиз"

    def test_share_code_not_found(self, db: Session, app_client):
        resp = app_client.get("/api/assignments/by-code/nonexistent")
        assert resp.status_code == 404

    def test_datetime_has_z_suffix(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 60,
        }, headers=headers).json()
        assert created["starts_at"].endswith("Z")
        assert created["ends_at"].endswith("Z")

    def test_change_time_limit(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "duration_minutes": 60,
        }, headers=headers).json()
        assert created["time_limit_minutes"] == 10

        resp = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"time_limit_minutes": 45},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["time_limit_minutes"] == 45

    def test_create_with_custom_time_limit(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 60,
            "time_limit_minutes": 20,
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["time_limit_minutes"] == 20

    def test_change_start_time_aborts_unfinished_attempts_and_recomputes_end(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        app_client.post(
            f"/api/groups/{group_id}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1"}]},
            headers=headers,
        )
        s_login = app_client.post("/api/auth/login", json={"username": "s1", "password": "pass"})
        s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=1)).isoformat(),
            "duration_minutes": 30,
        }, headers=headers).json()

        start = app_client.post(f"/api/assignments/{created['id']}/start", headers=s_headers).json()
        attempt_id = start["attempt_id"]
        token = start["session_token"]

        new_start = now + dt.timedelta(minutes=10)
        patch = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"starts_at": new_start.isoformat()},
            headers=headers,
        )
        assert patch.status_code == 200
        updated = patch.json()
        assert _parse_utc(updated["starts_at"]) == _parse_utc(new_start.isoformat())
        expected_end = _parse_utc(updated["starts_at"]) + dt.timedelta(minutes=updated["duration_minutes"])
        assert _parse_utc(updated["ends_at"]) == expected_end

        save_resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert save_resp.status_code == 404

    def test_export_results_csv(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        app_client.post(
            f"/api/groups/{group_id}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1"}]},
            headers=headers,
        )
        s_login = app_client.post("/api/auth/login", json={"username": "s1", "password": "pass"})
        s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "duration_minutes": 60,
        }, headers=headers).json()

        start = app_client.post(f"/api/assignments/{created['id']}/start", headers=s_headers).json()
        quiz_detail = app_client.get(f"/api/quizzes/{quiz_id}", headers=headers).json()
        by_id = {q["id"]: q for q in quiz_detail["questions"]}

        answers = []
        for q in start["questions"]:
            tq = by_id[q["id"]]
            if tq["q_type"] in ("single", "multiple"):
                correct_ids = [o["id"] for o in tq["options"] if o["is_correct"]]
                answers.append({"question_id": q["id"], "selected_option_ids": correct_ids})
            else:
                answers.append({"question_id": q["id"], "text_answer": tq["accepted_answers"][0]})

        submit = app_client.post(
            f"/api/attempts/{start['attempt_id']}/submit",
            json={"answers": answers},
            headers={**s_headers, "X-Session-Token": start["session_token"]},
        )
        assert submit.status_code == 200

        resp = app_client.get(f"/api/assignments/{created['id']}/results.csv", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers.get("content-disposition", "")

        rows = list(csv.reader(io.StringIO(resp.text.lstrip("\ufeff"))))
        assert len(rows) == 2
        header = rows[0]
        row = rows[1]
        assert header[:9] == [
            "student_id",
            "student_login",
            "attempt_id",
            "status",
            "score",
            "max_score",
            "correct_answers_count",
            "total_questions",
            "submitted_at",
        ]
        assert header[9:] == ["q1_correct", "q2_correct", "q3_correct"]
        assert row[1] == "s1"
        assert row[3] == "submitted"
        assert row[6] == "3"
        assert row[7] == "3"
        assert row[9:] == ["1", "1", "1"]
