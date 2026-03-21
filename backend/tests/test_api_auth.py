"""Tests for auth API endpoints."""

import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher, create_test_group, create_test_student


class TestLogin:
    def test_teacher_login_success(self, db: Session, app_client):
        create_test_teacher(db, "teach", "secret")
        resp = app_client.post("/api/auth/login", json={"username": "teach", "password": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "teacher"
        assert data["display_name"] == "Teach"
        assert "access_token" in data

    def test_student_login_success(self, db: Session, app_client):
        t = create_test_teacher(db)
        g = create_test_group(db, t.id)
        create_test_student(db, g.id, "stu", "pass")
        resp = app_client.post("/api/auth/login", json={"username": "stu", "password": "pass"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "student"

    def test_wrong_password(self, db: Session, app_client):
        create_test_teacher(db, "teach", "secret")
        resp = app_client.post("/api/auth/login", json={"username": "teach", "password": "wrong"})
        assert resp.status_code == 401

    def test_nonexistent_user(self, db: Session, app_client):
        resp = app_client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401

    def test_missing_fields(self, db: Session, app_client):
        resp = app_client.post("/api/auth/login", json={"username": "x"})
        assert resp.status_code == 422


class TestAuthProtection:
    def test_no_token_rejected(self, db: Session, app_client):
        resp = app_client.get("/api/quizzes")
        assert resp.status_code in (401, 403)

    def test_invalid_token_rejected(self, db: Session, app_client):
        resp = app_client.get("/api/quizzes", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401

    def test_student_cannot_access_teacher_routes(self, db: Session, app_client):
        t = create_test_teacher(db)
        g = create_test_group(db, t.id)
        create_test_student(db, g.id, "stu", "pass")
        login = app_client.post("/api/auth/login", json={"username": "stu", "password": "pass"})
        token = login.json()["access_token"]
        resp = app_client.get("/api/quizzes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
