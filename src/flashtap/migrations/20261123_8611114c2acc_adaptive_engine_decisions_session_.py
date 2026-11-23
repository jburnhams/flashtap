"""Adaptive engine: the decisions table, a session's policy and config, an attempt's decision
(src/flashtap/learners/models.py). Only additions: every existing row stays as it was, with nulls in the new columns.

Revision ID: 8611114c2acc
Revises: f5ed7c81b8ab
Create Date: 2026-11-23 17:19:10.406254

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8611114c2acc"
down_revision: str | Sequence[str] | None = "f5ed7c81b8ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("choices", sa.Integer(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("skill", sa.String(length=80), nullable=True),
        sa.Column("rationale", sa.JSON(), nullable=False),
        sa.Column("probability", sa.Double[float](), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name=op.f("fk_decisions_learner_id_learners"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], name=op.f("fk_decisions_session_id_sessions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisions")),
        sa.UniqueConstraint("session_id", "seq", name=op.f("uq_decisions_session_id_seq")),
    )
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_decisions_learner_id"), ["learner_id"], unique=False)

    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("decision_id", sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f("ix_attempts_decision_id"), ["decision_id"], unique=False)

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("policy", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("config", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("config")
        batch_op.drop_column("policy")

    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attempts_decision_id"))
        batch_op.drop_column("decision_id")

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_decisions_learner_id"))

    op.drop_table("decisions")
