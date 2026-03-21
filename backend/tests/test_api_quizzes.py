"""Tests for quiz CRUD API endpoints."""

import io
import pytest
from sqlalchemy.orm import Session

from tests.conftest import create_test_teacher, SAMPLE_QUIZ_MD


def _teacher_headers(app_client, db: Session) -> dict:
    create_test_teacher(db, "teach", "pass")
    resp = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestQuizImport:
    def test_import_success(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        resp = app_client.post(
            "/api/quizzes/import",
            files={"file": ("quiz.md", file, "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Тестовый квиз"
        assert data["question_count"] == 3
        assert len(data["questions"]) == 3

    def test_import_invalid_md(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(b"not a valid quiz")
        resp = app_client.post(
            "/api/quizzes/import",
            files={"file": ("bad.md", file, "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 422


class TestQuizList:
    def test_list_empty(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        resp = app_client.get("/api/quizzes", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_import(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        app_client.post("/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers)
        resp = app_client.get("/api/quizzes", headers=headers)
        assert len(resp.json()) == 1


class TestQuizDetail:
    def test_get_detail(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        created = app_client.post(
            "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers
        ).json()
        resp = app_client.get(f"/api/quizzes/{created['id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_md"] == SAMPLE_QUIZ_MD
        assert data["questions"][0]["options"][0]["is_correct"] is not None

    def test_get_nonexistent(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        resp = app_client.get("/api/quizzes/9999", headers=headers)
        assert resp.status_code == 404


class TestQuizDelete:
    def test_delete(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        created = app_client.post(
            "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers
        ).json()
        resp = app_client.delete(f"/api/quizzes/{created['id']}", headers=headers)
        assert resp.status_code == 204
        assert app_client.get(f"/api/quizzes/{created['id']}", headers=headers).status_code == 404


class TestQuizReimport:
    def test_reimport(self, db: Session, app_client):
        headers = _teacher_headers(app_client, db)
        file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
        created = app_client.post(
            "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers
        ).json()

        updated_md = SAMPLE_QUIZ_MD.replace("Тестовый квиз", "Новый тест")
        file2 = io.BytesIO(updated_md.encode())
        resp = app_client.post(
            f"/api/quizzes/{created['id']}/reimport",
            files={"file": ("q.md", file2, "text/markdown")},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Новый тест"
