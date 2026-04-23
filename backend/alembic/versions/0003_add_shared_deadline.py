"""Add Assignment.shared_deadline.

Adds a per-assignment switch for the deadline snapshot rule:

* ``shared_deadline = false`` (default) — each Attempt's ``deadline_at`` is
  ``started_at + duration_minutes``. Late starters get the full per-attempt
  clock. This is the historical behavior.
* ``shared_deadline = true`` — every Attempt's ``deadline_at`` is anchored to
  ``starts_at + duration_minutes``. The whole group ends at the same wall-clock
  moment; late starters have less time. In this mode the API also enforces
  ``start_window_minutes == duration_minutes`` so that the "Start" button
  cannot remain available past the shared deadline.

Existing rows are backfilled with ``false`` to preserve current semantics.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-23 04:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _assignments_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("assignments")}


def upgrade() -> None:
    bind = op.get_bind()
    if "shared_deadline" in _assignments_columns(bind):
        return

    # Use server_default=False so existing rows backfill safely without a
    # separate UPDATE pass; we then alter to NOT NULL (already implicit but
    # made explicit here for parity with the model definition).
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(
            sa.Column(
                "shared_deadline",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Drop the server_default so that future inserts go through the application
    # default (False) explicitly — keeps the schema source-of-truth in code.
    with op.batch_alter_table("assignments") as batch:
        batch.alter_column(
            "shared_deadline",
            existing_type=sa.Boolean(),
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "shared_deadline" not in _assignments_columns(bind):
        return
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("shared_deadline")
