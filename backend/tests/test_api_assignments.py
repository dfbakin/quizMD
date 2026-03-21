"""Tests for assignment CRUD API."""

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
