"""Snapshot per-attempt deadline_at and consolidate Assignment time fields.

Two changes happen atomically here:

1. `attempts.deadline_at` is added as `NOT NULL` and backfilled with the
   *historical* effective deadline rule:
       deadline = min(started_at + COALESCE(time_limit_minutes, duration_minutes), ends_at)
   This guarantees existing in-flight attempts retain the cutoff they
   originally saw, and submitted attempts get a defined value (which never
   gets read).

2. `assignments.time_limit_minutes` is collapsed into `duration_minutes`:
       duration_minutes := LEAST(duration_minutes, COALESCE(time_limit_minutes, duration_minutes))
   so that the new single-source-of-truth is the smaller of the two and
   future attempts get the same window students used to actually see.
   The legacy column is then dropped.

After this the application snapshots `deadline_at` at start and never
reaches into `Assignment` again to recompute it.

Revision ID: 0001
Revises:
Create Date: 2026-04-23 00:00:00.000000
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _attempts_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("attempts")}


def _assignments_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("assignments")}


def _to_dt(value) -> dt.datetime | None:
    """SQLite returns datetimes as strings; Postgres returns proper datetimes."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    return dt.datetime.fromisoformat(str(value))


def upgrade() -> None:
    bind = op.get_bind()
    attempt_cols = _attempts_columns(bind)
    assignment_cols = _assignments_columns(bind)

    # ---- 1. Add attempts.deadline_at (nullable for backfill) -------------
    if "deadline_at" not in attempt_cols:
        with op.batch_alter_table("attempts") as batch:
            batch.add_column(sa.Column("deadline_at", sa.DateTime(), nullable=True))

    # ---- 2. Backfill deadline_at using historical rule -------------------
    # Two-pass: assignments first (so we can read time_limit_minutes if it
    # still exists), then attempts.
    has_old_tlm = "time_limit_minutes" in assignment_cols

    if has_old_tlm:
        assignments = bind.execute(
            sa.text(
                "SELECT id, ends_at, duration_minutes, time_limit_minutes "
                "FROM assignments"
            )
        ).mappings().all()
    else:
        assignments = bind.execute(
            sa.text(
                "SELECT id, ends_at, duration_minutes, NULL AS time_limit_minutes "
                "FROM assignments"
            )
        ).mappings().all()

    a_by_id = {row["id"]: row for row in assignments}

    attempts = bind.execute(
        sa.text(
            "SELECT id, assignment_id, started_at, submitted_at, deadline_at "
            "FROM attempts"
        )
    ).mappings().all()

    for att in attempts:
        if att["deadline_at"] is not None:
            continue
        a = a_by_id.get(att["assignment_id"])
        started = _to_dt(att["started_at"]) or dt.datetime.utcnow()
        if a is None:
            # Orphan attempt — pick a safe past deadline so the row can
            # become NOT NULL. The app's auto-grade sweep will tidy it.
            deadline = started
        else:
            duration = a["duration_minutes"] or 0
            tlm = a["time_limit_minutes"]
            effective_minutes = duration if tlm is None else min(duration, tlm)
            ends = _to_dt(a["ends_at"])
            by_attempt = started + dt.timedelta(minutes=effective_minutes)
            deadline = min(by_attempt, ends) if ends is not None else by_attempt

        bind.execute(
            sa.text("UPDATE attempts SET deadline_at = :d WHERE id = :id"),
            {"d": deadline, "id": att["id"]},
        )

    # ---- 3. Make attempts.deadline_at NOT NULL ---------------------------
    with op.batch_alter_table("attempts") as batch:
        batch.alter_column("deadline_at", existing_type=sa.DateTime(), nullable=False)

    # ---- 4. Collapse assignments.duration_minutes ------------------------
    if has_old_tlm:
        bind.execute(
            sa.text(
                "UPDATE assignments "
                "SET duration_minutes = CASE "
                "  WHEN time_limit_minutes IS NULL THEN duration_minutes "
                "  WHEN time_limit_minutes < duration_minutes THEN time_limit_minutes "
                "  ELSE duration_minutes "
                "END"
            )
        )
        # Recompute ends_at to match the (possibly shortened) duration so the
        # start-window close stays consistent with the new semantics.
        bind.execute(
            sa.text(
                "UPDATE assignments "
                "SET ends_at = datetime(starts_at, '+' || duration_minutes || ' minutes')"
            ) if bind.dialect.name == "sqlite" else sa.text(
                "UPDATE assignments "
                "SET ends_at = starts_at + (duration_minutes * interval '1 minute')"
            )
        )

        # ---- 5. Drop assignments.time_limit_minutes ----------------------
        with op.batch_alter_table("assignments") as batch:
            batch.drop_column("time_limit_minutes")


def downgrade() -> None:
    bind = op.get_bind()
    assignment_cols = _assignments_columns(bind)
    attempt_cols = _attempts_columns(bind)

    if "time_limit_minutes" not in assignment_cols:
        with op.batch_alter_table("assignments") as batch:
            batch.add_column(sa.Column("time_limit_minutes", sa.Integer(), nullable=True))
        # Best-effort: copy duration_minutes into time_limit_minutes so the
        # old hybrid rule still produces the same effective deadline.
        bind.execute(
            sa.text(
                "UPDATE assignments SET time_limit_minutes = duration_minutes"
            )
        )

    if "deadline_at" in attempt_cols:
        with op.batch_alter_table("attempts") as batch:
            batch.drop_column("deadline_at")
