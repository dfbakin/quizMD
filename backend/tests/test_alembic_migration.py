"""Integration test for the 0001 + 0002 + 0003 schema migrations.

Builds a SQLite DB with the OLD schema, seeds rows whose shape mirrors a real
production sample, runs `alembic upgrade head` programmatically (which applies
0001 → 0002 → 0003), and asserts both the schema and the backfilled data.

Tests both directions: upgrade and downgrade.
"""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


def _create_old_schema(engine: sa.Engine) -> None:
    """Mirror of the pre-migration schema."""
    statements = [
        """CREATE TABLE teachers (
            id INTEGER PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(200) NOT NULL
        )""",
        """CREATE TABLE groups (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            teacher_id INTEGER NOT NULL REFERENCES teachers(id)
        )""",
        """CREATE TABLE students (
            id INTEGER PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            group_id INTEGER NOT NULL REFERENCES groups(id)
        )""",
        """CREATE TABLE quizzes (
            id INTEGER PRIMARY KEY,
            title VARCHAR(300) NOT NULL,
            source_md TEXT NOT NULL,
            time_limit_minutes INTEGER,
            shuffle_questions BOOLEAN DEFAULT 0,
            shuffle_answers BOOLEAN DEFAULT 0,
            teacher_id INTEGER NOT NULL REFERENCES teachers(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE assignments (
            id INTEGER PRIMARY KEY,
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            group_id INTEGER NOT NULL REFERENCES groups(id),
            starts_at DATETIME NOT NULL,
            ends_at DATETIME NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            time_limit_minutes INTEGER,
            results_visible BOOLEAN DEFAULT 0,
            share_code VARCHAR(20) UNIQUE NOT NULL
        )""",
        """CREATE TABLE assignment_student_views (
            assignment_id INTEGER PRIMARY KEY REFERENCES assignments(id),
            student_view_mode VARCHAR(20) NOT NULL DEFAULT 'closed'
        )""",
        """CREATE TABLE attempts (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            assignment_id INTEGER NOT NULL REFERENCES assignments(id),
            session_token VARCHAR(100) UNIQUE NOT NULL,
            shuffle_seed VARCHAR(100) NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            submitted_at DATETIME,
            score FLOAT
        )""",
        """CREATE TABLE answers (
            id INTEGER PRIMARY KEY,
            attempt_id INTEGER NOT NULL REFERENCES attempts(id),
            question_id INTEGER NOT NULL,
            selected_option_ids JSON,
            text_answer VARCHAR(500),
            is_correct BOOLEAN,
            points_awarded INTEGER DEFAULT 0
        )""",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(sa.text(stmt))


# Four shapes hit by the migration that mirror real production rows.
_BASE = dt.datetime(2026, 4, 22, 8, 0, 0)
_ASSIGNMENT_FIXTURES = [
    # (id, duration_minutes, time_limit_minutes, ends_offset_min)
    (17, 10, 30, 10),       # tlm > duration -> effective = duration = 10
    (15, 45, 15, 45),       # tlm < duration -> effective = tlm = 15
    (1, 1440, None, 1440),  # no tlm -> effective = duration
    (2, 604800, 5, 604800), # open-ended duration with short tlm -> effective = 5
]
_ATTEMPT_FIXTURES = [
    # (id, assignment_id, started_offset_min, submitted_offset_min, expected_deadline_min)
    (101, 17, 0, None, 10),
    (102, 15, 0, None, 15),
    (103, 1, 0, None, 1440),
    (104, 2, 0, None, 5),
    (105, 17, 0, 3, 10),
    (106, 15, 20, None, 35),  # started 20 min late, +15 = 35
]


def _seed(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO teachers (id, username, password_hash, display_name) VALUES (1, 't', 'h', 'T')"
        ))
        conn.execute(sa.text("INSERT INTO groups (id, name, teacher_id) VALUES (1, 'G1', 1)"))
        conn.execute(sa.text(
            "INSERT INTO students (id, username, password_hash, display_name, group_id) "
            "VALUES (1, 's1', 'h', 'S1', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO quizzes (id, title, source_md, teacher_id) VALUES (1, 'Q', 'md', 1)"
        ))
        for aid, dur, tlm, end_off in _ASSIGNMENT_FIXTURES:
            ends = _BASE + dt.timedelta(minutes=end_off)
            conn.execute(sa.text(
                "INSERT INTO assignments (id, quiz_id, group_id, starts_at, ends_at, "
                "duration_minutes, time_limit_minutes, share_code) "
                "VALUES (:id, 1, 1, :s, :e, :d, :t, :c)"
            ), {"id": aid, "s": _BASE, "e": ends, "d": dur, "t": tlm, "c": f"sc{aid}"})
        for att_id, ass_id, start_off, sub_off, _ in _ATTEMPT_FIXTURES:
            started = _BASE + dt.timedelta(minutes=start_off)
            sub = _BASE + dt.timedelta(minutes=sub_off) if sub_off is not None else None
            conn.execute(sa.text(
                "INSERT INTO attempts (id, student_id, assignment_id, session_token, "
                "shuffle_seed, started_at, submitted_at) "
                "VALUES (:id, 1, :aid, :tok, :seed, :s, :sub)"
            ), {
                "id": att_id, "aid": ass_id,
                "tok": f"tok{att_id}", "seed": f"seed{att_id}",
                "s": started, "sub": sub,
            })


def _to_dt(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    return dt.datetime.fromisoformat(str(value))


@pytest.fixture()
def migration_engine(tmp_path: pathlib.Path) -> Iterator[sa.Engine]:
    db_path = tmp_path / "alembic_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = sa.create_engine(db_url)
    _create_old_schema(engine)
    _seed(engine)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.attributes["url_override"] = db_url

    # Bypass app.config.settings reading $DATABASE_URL by patching env.py at
    # runtime via a side-channel: we set the URL on the config and let the
    # env.py re-read it. env.py currently sets it from settings, so override
    # AFTER load by injecting via env-var as well.
    import os as _os
    _os.environ["DATABASE_URL"] = db_url

    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


class TestZeroOneSchemaMigration:
    def test_drops_assignment_time_limit_minutes(self, migration_engine: sa.Engine):
        cols = {c["name"] for c in sa.inspect(migration_engine).get_columns("assignments")}
        assert "time_limit_minutes" not in cols

    def test_adds_attempt_deadline_at_not_null(self, migration_engine: sa.Engine):
        cols = {c["name"]: c for c in sa.inspect(migration_engine).get_columns("attempts")}
        assert "deadline_at" in cols
        assert cols["deadline_at"]["nullable"] is False

    def test_collapses_duration_to_least_of_old_pair(self, migration_engine: sa.Engine):
        with migration_engine.connect() as conn:
            rows = {r["id"]: r["duration_minutes"] for r in conn.execute(
                sa.text("SELECT id, duration_minutes FROM assignments")
            ).mappings()}
        assert rows[17] == 10
        assert rows[15] == 15
        assert rows[1] == 1440
        assert rows[2] == 5

    def test_recomputes_ends_at_to_match_new_duration(self, migration_engine: sa.Engine):
        with migration_engine.connect() as conn:
            rows = {r["id"]: r for r in conn.execute(
                sa.text("SELECT id, starts_at, ends_at, duration_minutes FROM assignments")
            ).mappings()}
        for aid in (17, 15, 1, 2):
            row = rows[aid]
            ends = _to_dt(row["ends_at"])
            starts = _to_dt(row["starts_at"])
            assert ends - starts == dt.timedelta(minutes=row["duration_minutes"])

    def test_backfills_deadline_at_per_historical_hybrid_rule(self, migration_engine: sa.Engine):
        with migration_engine.connect() as conn:
            rows = {r["id"]: r["deadline_at"] for r in conn.execute(
                sa.text("SELECT id, deadline_at FROM attempts")
            ).mappings()}
        for att_id, _, _, _, expected_off in _ATTEMPT_FIXTURES:
            assert _to_dt(rows[att_id]) == _BASE + dt.timedelta(minutes=expected_off)


class TestZeroTwoStartWindowMigration:
    def test_adds_start_window_minutes_not_null(self, migration_engine: sa.Engine):
        cols = {c["name"]: c for c in sa.inspect(migration_engine).get_columns("assignments")}
        assert "start_window_minutes" in cols
        assert cols["start_window_minutes"]["nullable"] is False

    def test_backfills_start_window_to_post_0001_duration(self, migration_engine: sa.Engine):
        """After 0001 collapses duration to LEAST(duration, time_limit), 0002
        copies that value into start_window_minutes — preserving the historical
        ``starts_at + duration_minutes == ends_at`` invariant exactly."""
        with migration_engine.connect() as conn:
            rows = {r["id"]: r for r in conn.execute(
                sa.text(
                    "SELECT id, duration_minutes, start_window_minutes "
                    "FROM assignments"
                )
            ).mappings()}
        for aid in (17, 15, 1, 2):
            assert rows[aid]["start_window_minutes"] == rows[aid]["duration_minutes"]


class TestZeroThreeSharedDeadlineMigration:
    def test_adds_shared_deadline_not_null(self, migration_engine: sa.Engine):
        cols = {c["name"]: c for c in sa.inspect(migration_engine).get_columns("assignments")}
        assert "shared_deadline" in cols
        assert cols["shared_deadline"]["nullable"] is False

    def test_backfills_existing_rows_to_false(self, migration_engine: sa.Engine):
        """Pre-existing assignments retain the historical per-student timer
        semantics — only opt-in flips a row into shared mode."""
        with migration_engine.connect() as conn:
            rows = list(conn.execute(
                sa.text("SELECT id, shared_deadline FROM assignments")
            ).mappings())
        # Every seeded fixture must come back as not-shared.
        assert {bool(r["shared_deadline"]) for r in rows} == {False}


class TestDowngrade:
    def test_full_downgrade_restores_columns(self, tmp_path: pathlib.Path):
        db_path = tmp_path / "alembic_down.db"
        db_url = f"sqlite:///{db_path}"
        engine = sa.create_engine(db_url)
        _create_old_schema(engine)
        _seed(engine)
        engine.dispose()

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("sqlalchemy.url", db_url)
        import os as _os
        _os.environ["DATABASE_URL"] = db_url

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        engine = sa.create_engine(db_url)
        assignment_cols = {c["name"] for c in sa.inspect(engine).get_columns("assignments")}
        attempt_cols = {c["name"] for c in sa.inspect(engine).get_columns("attempts")}
        assert "time_limit_minutes" in assignment_cols
        assert "start_window_minutes" not in assignment_cols
        assert "shared_deadline" not in assignment_cols
        assert "deadline_at" not in attempt_cols
        engine.dispose()
