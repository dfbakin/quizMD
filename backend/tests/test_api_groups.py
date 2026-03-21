"""Tests for group and student management API."""

import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher


def _teacher_headers(app_client, db: Session) -> dict:
    create_test_teacher(db, "teach", "pass")
    resp = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestGroups:
    def test_create_group(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        resp = app_client.post("/api/groups", json={"name": "11А"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "11А"

    def test_list_groups(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        app_client.post("/api/groups", json={"name": "11А"}, headers=headers)
        app_client.post("/api/groups", json={"name": "11Б"}, headers=headers)
        resp = app_client.get("/api/groups", headers=headers)
        assert len(resp.json()) == 2

    def test_delete_group(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        created = app_client.post("/api/groups", json={"name": "11А"}, headers=headers).json()
        resp = app_client.delete(f"/api/groups/{created['id']}", headers=headers)
        assert resp.status_code == 204


class TestStudents:
    def test_add_students(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        group = app_client.post("/api/groups", json={"name": "11А"}, headers=headers).json()
        resp = app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [
                {"username": "s1", "password": "pass", "display_name": "Student 1"},
                {"username": "s2", "password": "pass", "display_name": "Student 2"},
            ]},
            headers=headers,
        )
        assert resp.status_code == 201
        assert len(resp.json()) == 2

    def test_list_students(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        group = app_client.post("/api/groups", json={"name": "11А"}, headers=headers).json()
        app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1"}]},
            headers=headers,
        )
        resp = app_client.get(f"/api/groups/{group['id']}/students", headers=headers)
        assert len(resp.json()) == 1

    def test_duplicate_username_rejected(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        group = app_client.post("/api/groups", json={"name": "11А"}, headers=headers).json()
        app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1"}]},
            headers=headers,
        )
        resp = app_client.post(
            f"/api/groups/{group['id']}/students",
            json={"students": [{"username": "s1", "password": "pass", "display_name": "S1 dup"}]},
            headers=headers,
        )
        assert resp.status_code == 409
