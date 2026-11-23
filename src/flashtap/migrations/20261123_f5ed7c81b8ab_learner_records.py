"""Learner records: learners, sessions, attempts and tombstones (src/flashtap/learners/models.py).

Revision ID: f5ed7c81b8ab
Revises:
Create Date: 2026-11-23 13:56:02.409331
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5ed7c81b8ab"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "learners",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("nickname", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learners")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name=op.f("fk_sessions_learner_id_learners"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_learner_id"), ["learner_id"], unique=False)

    op.create_table(
        "attempts",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("choices", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("mechanic", sa.String(length=32), nullable=False),
        sa.Column("options", sa.Integer(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("asked", sa.String(length=32), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_answer", sa.JSON(), nullable=False),
        sa.Column("first_correct", sa.Boolean(), nullable=False),
        sa.Column("tries", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name=op.f("fk_attempts_learner_id_learners"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_attempts_session_id_sessions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_attempts")),
    )
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.create_index("ix_attempts_learner_id_presented_at", ["learner_id", "presented_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_attempts_session_id"), ["session_id"], unique=False)

    op.create_table(
        "tombstones",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["attempts.event_id"], name=op.f("fk_tombstones_event_id_attempts"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_tombstones")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tombstones")
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attempts_session_id"))
        batch_op.drop_index("ix_attempts_learner_id_presented_at")

    op.drop_table("attempts")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_learner_id"))

    op.drop_table("sessions")
    op.drop_table("learners")
