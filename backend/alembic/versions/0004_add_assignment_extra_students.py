"""Add assignment_extra_students.

Adds a many-to-many join table letting a teacher attach individual students to
an existing assignment without touching anyone's ``Student.group_id``. The
access rule becomes: a student sees/starts an assignment iff
``assignment.group_id == student.group_id`` OR a row exists in this table for
``(assignment_id, student_id)``.

Both foreign keys use ``ON DELETE CASCADE`` so deleting either side cleans up
the override row automatically. Nothing existing is modified; the table is
empty at migration time.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-29 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return name in set(inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "assignment_extra_students"):
        return

    # Using explicit Constraint objects (rather than inline FKs on the
    # Column) so SQLAlchemy reflects the FK + PK metadata back reliably on
    # both SQLite and Postgres. The DDL emitted is equivalent.
    op.create_table(
        "assignment_extra_students",
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"],
            ondelete="CASCADE",
            name="fk_assignment_extra_students_assignment_id",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"],
            ondelete="CASCADE",
            name="fk_assignment_extra_students_student_id",
        ),
        sa.PrimaryKeyConstraint(
            "assignment_id", "student_id",
            name="pk_assignment_extra_students",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "assignment_extra_students"):
        return
    op.drop_table("assignment_extra_students")
