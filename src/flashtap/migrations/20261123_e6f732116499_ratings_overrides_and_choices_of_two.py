"""Ratings, a grown-up's overrides and choices of two (plan PR 6, P4; src/flashtap/learners/models.py): two new
tables, `ratings` (the three faces after a round) and `overrides` (a grown-up's observation of a skill), and four
columns on `decisions` for a choice between two activities: the two rounds offered, which one was picked and when,
and whether to ask how the round was.

Existing decisions are rounds, breaks and ends: none offered a choice or asked for a rating, so the new columns are
None and false for them, which is what `rate`'s server default gives. `sa.false()` rather than `text("0")`: Postgres
refuses an integer default on a boolean.

Revision ID: e6f732116499
Revises: ad08d3806978
Create Date: 2026-11-23 19:12:10.536943

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f732116499"
down_revision: str | Sequence[str] | None = "ad08d3806978"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("skill", sa.String(length=80), nullable=False),
        sa.Column("says", sa.String(length=16), nullable=False),
        sa.Column("observer", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name=op.f("fk_overrides_learner_id_learners"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_overrides")),
    )
    with op.batch_alter_table("overrides", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_overrides_learner_id"), ["learner_id"], unique=False)

    op.create_table(
        "ratings",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("scale", sa.String(length=16), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["attempts.event_id"], name=op.f("fk_ratings_event_id_attempts"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name=op.f("fk_ratings_learner_id_learners"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", "scale", name=op.f("pk_ratings")),
    )
    with op.batch_alter_table("ratings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ratings_learner_id"), ["learner_id"], unique=False)

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("offers", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("picked", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rate", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_column("rate")
        batch_op.drop_column("picked_at")
        batch_op.drop_column("picked")
        batch_op.drop_column("offers")

    with op.batch_alter_table("ratings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ratings_learner_id"))

    op.drop_table("ratings")
    with op.batch_alter_table("overrides", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_overrides_learner_id"))

    op.drop_table("overrides")
