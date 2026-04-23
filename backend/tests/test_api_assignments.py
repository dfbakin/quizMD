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
        assert data["student_view_mode"] == "closed"
        assert data["in_progress_attempts"] == 0
        assert "share_code" in data
        assert "time_limit_minutes" not in data

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

    def test_change_duration_minutes(self, db: Session, app_client):
        """Changing the per-attempt clock must NOT shift ends_at (the start
        window close). Otherwise a teacher tightening the per-attempt timer
        for late-joiners would silently shorten when others are allowed to
        begin."""
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "duration_minutes": 60,
        }, headers=headers).json()
        original_ends_at = created["ends_at"]
        original_window = created["start_window_minutes"]

        resp = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"duration_minutes": 45},
            headers=headers,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["duration_minutes"] == 45
        # ends_at and start_window_minutes are unchanged — only the per-attempt
        # clock was edited.
        assert updated["ends_at"] == original_ends_at
        assert updated["start_window_minutes"] == original_window

    def test_change_start_window_minutes_recomputes_ends_at(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "start_window_minutes": 30,
            "duration_minutes": 60,
        }, headers=headers).json()
        assert created["start_window_minutes"] == 30
        starts = _parse_utc(created["starts_at"])
        assert _parse_utc(created["ends_at"]) == starts + dt.timedelta(minutes=30)

        resp = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"start_window_minutes": 90},
            headers=headers,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["start_window_minutes"] == 90
        # Only the start window changed; the per-attempt clock is unchanged.
        assert updated["duration_minutes"] == 60
        assert _parse_utc(updated["ends_at"]) == starts + dt.timedelta(minutes=90)

    def test_create_with_explicit_start_window_distinct_from_duration(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(),
            "start_window_minutes": 90,
            "duration_minutes": 30,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["start_window_minutes"] == 90
        assert data["duration_minutes"] == 30
        starts = _parse_utc(data["starts_at"])
        assert _parse_utc(data["ends_at"]) == starts + dt.timedelta(minutes=90)

    def test_create_omitting_start_window_defaults_to_duration(self, db: Session, app_client):
        """Backward-compatibility shim: callers that don't yet know about
        start_window_minutes get the old conflated semantics."""
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(),
            "duration_minutes": 45,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["start_window_minutes"] == 45
        assert data["duration_minutes"] == 45

    def test_create_rejects_nonpositive_start_window(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        resp = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(),
            "start_window_minutes": 0,
            "duration_minutes": 30,
        }, headers=headers)
        assert resp.status_code == 422

    def test_create_default_shared_deadline_is_false(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(),
            "duration_minutes": 30,
        }, headers=headers).json()
        assert created["shared_deadline"] is False

    def test_change_start_time_with_no_open_attempts_does_not_require_choice(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": (now - dt.timedelta(minutes=1)).isoformat(),
            "duration_minutes": 30,
        }, headers=headers).json()

        new_start = now + dt.timedelta(minutes=10)
        patch = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"starts_at": new_start.isoformat()},
            headers=headers,
        )
        assert patch.status_code == 200
        updated = patch.json()
        assert _parse_utc(updated["starts_at"]) == _parse_utc(new_start.isoformat())
        assert _parse_utc(updated["ends_at"]) == (
            _parse_utc(updated["starts_at"]) + dt.timedelta(minutes=updated["duration_minutes"])
        )

    def test_change_start_time_with_open_attempts_requires_explicit_choice(self, db: Session, app_client):
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

        app_client.post(f"/api/assignments/{created['id']}/start", headers=s_headers).json()

        new_start = now + dt.timedelta(minutes=10)
        no_choice = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"starts_at": new_start.isoformat()},
            headers=headers,
        )
        assert no_choice.status_code == 422
        assert "in-progress" in no_choice.json()["detail"]

    def test_change_start_time_reset_deletes_open_attempts(self, db: Session, app_client):
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
            json={"starts_at": new_start.isoformat(), "on_open_attempts": "reset"},
            headers=headers,
        )
        assert patch.status_code == 200
        assert patch.json()["in_progress_attempts"] == 0

        save_resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert save_resp.status_code == 404

    def test_change_start_time_keep_preserves_open_attempts_and_their_deadline(self, db: Session, app_client):
        from app.models import Attempt
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
        original_deadline = _parse_utc(start["deadline_at"])

        new_start = now + dt.timedelta(minutes=10)
        patch = app_client.patch(
            f"/api/assignments/{created['id']}",
            json={"starts_at": new_start.isoformat(), "on_open_attempts": "keep"},
            headers=headers,
        )
        assert patch.status_code == 200
        assert patch.json()["in_progress_attempts"] == 1

        # The attempt is still active and saving still works against its snapshot deadline.
        save_resp = app_client.post(
            f"/api/attempts/{attempt_id}/save",
            json={"answers": []},
            headers={**s_headers, "X-Session-Token": token},
        )
        assert save_resp.status_code == 200

        att = db.get(Attempt, attempt_id)
        assert att is not None
        assert att.deadline_at.replace(tzinfo=None) == original_deadline.replace(tzinfo=None)

    def test_create_exposes_extra_student_count_zero_by_default(self, db: Session, app_client):
        headers, quiz_id, group_id = _setup(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()
        assert created["extra_student_count"] == 0

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


def _setup_two_groups(app_client, db: Session):
    """Shared fixture for extras tests: teacher with two of their own groups
    plus one student in each. Returns (headers, quiz_id, group_a_id, group_b_id,
    student_a_id, student_b_id). Student A lives in group A, student B in B."""
    create_test_teacher(db, "teach", "pass")
    login = app_client.post("/api/auth/login", json={"username": "teach", "password": "pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    group_a = app_client.post("/api/groups", json={"name": "10А"}, headers=headers).json()
    group_b = app_client.post("/api/groups", json={"name": "10Б"}, headers=headers).json()
    file = io.BytesIO(SAMPLE_QUIZ_MD.encode())
    quiz = app_client.post(
        "/api/quizzes/import", files={"file": ("q.md", file, "text/markdown")}, headers=headers,
    ).json()

    app_client.post(
        f"/api/groups/{group_a['id']}/students",
        json={"students": [{"username": "alice", "password": "pw", "display_name": "Alice"}]},
        headers=headers,
    )
    app_client.post(
        f"/api/groups/{group_b['id']}/students",
        json={"students": [{"username": "bob", "password": "pw", "display_name": "Bob"}]},
        headers=headers,
    )
    from app.models import Student
    alice = db.query(Student).filter_by(username="alice").first()
    bob = db.query(Student).filter_by(username="bob").first()
    return headers, quiz["id"], group_a["id"], group_b["id"], alice.id, bob.id


class TestAssignmentExtrasCRUD:
    """End-to-end tests for the per-student access override (AssignmentExtraStudent).

    The scenario that drives this feature: assignment A belongs to group_a;
    Bob lives in group_b; teacher adds Bob as an extra so he can participate
    in this one assignment without touching his home group.
    """

    def test_list_is_empty_by_default(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, _ = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        resp = app_client.get(f"/api/assignments/{created['id']}/extras", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_extra_student_from_other_group(self, db: Session, app_client):
        headers, quiz_id, group_a_id, group_b_id, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        resp = app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": bob_id},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == bob_id
        assert body["display_name"] == "Bob"
        assert body["home_group_id"] == group_b_id
        assert body["home_group_name"] == "10Б"

        # AssignmentOut.extra_student_count reflects the new row immediately.
        listing = app_client.get("/api/assignments", headers=headers).json()
        assert listing[0]["extra_student_count"] == 1

    def test_add_is_idempotent(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        for _ in range(3):
            r = app_client.post(
                f"/api/assignments/{created['id']}/extras",
                json={"student_id": bob_id},
                headers=headers,
            )
            assert r.status_code == 201
        extras = app_client.get(f"/api/assignments/{created['id']}/extras", headers=headers).json()
        assert len(extras) == 1

    def test_adding_a_student_from_home_group_is_noop(self, db: Session, app_client):
        """Students already in the assignment's home group don't need extras —
        the endpoint returns success but creates no row, so the UI stays
        consistent if a teacher accidentally picks a home-group student."""
        headers, quiz_id, group_a_id, _, alice_id, _ = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        r = app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": alice_id},
            headers=headers,
        )
        assert r.status_code == 201
        extras = app_client.get(f"/api/assignments/{created['id']}/extras", headers=headers).json()
        assert extras == []

    def test_add_rejects_student_not_owned_by_teacher(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, _ = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        # Second teacher with their own group + student.
        create_test_teacher(db, "other", "pass")
        other_login = app_client.post(
            "/api/auth/login", json={"username": "other", "password": "pass"},
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
        other_group = app_client.post(
            "/api/groups", json={"name": "O"}, headers=other_headers,
        ).json()
        app_client.post(
            f"/api/groups/{other_group['id']}/students",
            json={"students": [{"username": "charlie", "password": "pw", "display_name": "Charlie"}]},
            headers=other_headers,
        )
        from app.models import Student
        charlie = db.query(Student).filter_by(username="charlie").first()

        resp = app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": charlie.id},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_remove_extra(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()
        app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": bob_id}, headers=headers,
        )
        resp = app_client.delete(
            f"/api/assignments/{created['id']}/extras/{bob_id}", headers=headers,
        )
        assert resp.status_code == 204
        extras = app_client.get(f"/api/assignments/{created['id']}/extras", headers=headers).json()
        assert extras == []

    def test_remove_nonexistent_is_idempotent(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()
        resp = app_client.delete(
            f"/api/assignments/{created['id']}/extras/{bob_id}", headers=headers,
        )
        assert resp.status_code == 204

    def test_delete_assignment_cascades_extras(self, db: Session, app_client):
        from app.models import AssignmentExtraStudent
        headers, quiz_id, group_a_id, _, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()
        app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": bob_id}, headers=headers,
        )
        assert db.query(AssignmentExtraStudent).count() == 1

        app_client.delete(f"/api/assignments/{created['id']}", headers=headers)
        assert db.query(AssignmentExtraStudent).count() == 0

    def test_cross_teacher_cannot_see_or_touch_extras(self, db: Session, app_client):
        headers, quiz_id, group_a_id, _, _, bob_id = _setup_two_groups(app_client, db)
        now = dt.datetime.now(dt.timezone.utc)
        created = app_client.post("/api/assignments", json={
            "quiz_id": quiz_id, "group_id": group_a_id,
            "starts_at": now.isoformat(), "duration_minutes": 30,
        }, headers=headers).json()

        create_test_teacher(db, "other", "pass")
        other_login = app_client.post(
            "/api/auth/login", json={"username": "other", "password": "pass"},
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        get_resp = app_client.get(
            f"/api/assignments/{created['id']}/extras", headers=other_headers,
        )
        assert get_resp.status_code == 404
        post_resp = app_client.post(
            f"/api/assignments/{created['id']}/extras",
            json={"student_id": bob_id}, headers=other_headers,
        )
        assert post_resp.status_code == 404
        del_resp = app_client.delete(
            f"/api/assignments/{created['id']}/extras/{bob_id}", headers=other_headers,
        )
        assert del_resp.status_code == 404


class TestTeacherStudentSearch:
    """Autocomplete behind /api/my/students."""

    def test_search_returns_only_own_students(self, db: Session, app_client):
        headers, _, _, _, _, _ = _setup_two_groups(app_client, db)

        # Second teacher with their own students — must not leak.
        create_test_teacher(db, "other", "pass")
        other_login = app_client.post(
            "/api/auth/login", json={"username": "other", "password": "pass"},
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
        other_group = app_client.post(
            "/api/groups", json={"name": "X"}, headers=other_headers,
        ).json()
        app_client.post(
            f"/api/groups/{other_group['id']}/students",
            json={"students": [{"username": "xyz", "password": "pw", "display_name": "XYZ"}]},
            headers=other_headers,
        )

        resp = app_client.get("/api/my/students", headers=headers)
        assert resp.status_code == 200
        names = {r["username"] for r in resp.json()}
        assert names == {"alice", "bob"}

    def test_search_filters_by_substring_case_insensitive(self, db: Session, app_client):
        headers, _, _, _, _, _ = _setup_two_groups(app_client, db)
        resp = app_client.get("/api/my/students?q=bo", headers=headers)
        assert [r["username"] for r in resp.json()] == ["bob"]

    def test_search_includes_home_group_name(self, db: Session, app_client):
        headers, _, group_a_id, group_b_id, _, _ = _setup_two_groups(app_client, db)
        resp = app_client.get("/api/my/students?q=bob", headers=headers).json()
        assert len(resp) == 1
        assert resp[0]["group_id"] == group_b_id
        assert resp[0]["group_name"] == "10Б"

    def test_search_limit_is_respected(self, db: Session, app_client):
        headers, _, group_a_id, _, _, _ = _setup_two_groups(app_client, db)
        for i in range(5):
            app_client.post(
                f"/api/groups/{group_a_id}/students",
                json={"students": [{"username": f"extra{i}", "password": "pw", "display_name": f"Extra{i}"}]},
                headers=headers,
            )
        resp = app_client.get("/api/my/students?limit=3", headers=headers).json()
        assert len(resp) == 3
