"""Decouple the per-attempt clock from the start window.

Before this migration, Assignment had a single ``duration_minutes`` that played
two roles: it bounded how long after ``starts_at`` a student could *begin* an
attempt, AND it was the per-attempt timer once started. That conflation made it
impossible to express "open this 30-min quiz for the entire class period".

This migration adds ``Assignment.start_window_minutes`` and backfills it with
``duration_minutes`` so existing assignments preserve their current behavior
exactly (``ends_at`` was already ``starts_at + duration_minutes``, which now
equals ``starts_at + start_window_minutes`` — no recomputation needed).

After this:
 - ``start_window_minutes`` controls when the *Start* button is allowed.
   ``Assignment.ends_at`` is recomputed from it on create/update.
 - ``duration_minutes`` controls only the per-attempt clock, which the start
   handler still snapshots into ``Attempt.deadline_at``.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-23 03:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _assignments_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("assignments")}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _assignments_columns(bind)

    if "start_window_minutes" in cols:
        return

    # Add as nullable so we can backfill existing rows; tighten to NOT NULL
    # afterwards. batch_alter_table is required for SQLite.
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("start_window_minutes", sa.Integer(), nullable=True))

    # Backfill: every existing assignment kept the old "start window == attempt
    # duration" semantics, so copy duration into start_window_minutes. This
    # also means ends_at (== starts_at + duration_minutes pre-migration) is
    # already consistent with starts_at + start_window_minutes — no
    # recomputation needed.
    bind.execute(
        sa.text(
            "UPDATE assignments SET start_window_minutes = duration_minutes "
            "WHERE start_window_minutes IS NULL"
        )
    )

    with op.batch_alter_table("assignments") as batch:
        batch.alter_column(
            "start_window_minutes",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _assignments_columns(bind)
    if "start_window_minutes" not in cols:
        return
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("start_window_minutes")
