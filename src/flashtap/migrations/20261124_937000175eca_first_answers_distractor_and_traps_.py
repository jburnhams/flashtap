"""Mistakes read as misconceptions (0.12.0; src/flashtap/mistakes.py): on `attempts`, `distractor` (the generator that
chose the option first tapped, "" when it was right) and `traps` (each misconception a wrong option of the round could
show, with those options' ids); on `decisions`, `probe` (a misconception the engine chose the round to check).

Nullable with no default and no backfill: an attempt from before was judged without them, and None means "not
recorded", so it gives no evidence of a misconception and every older estimate, state and decision rebuilds unchanged.

Revision ID: 937000175eca
Revises: 69aa91735931
Create Date: 2026-11-24 09:55:51.633881

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "937000175eca"
down_revision: str | Sequence[str] | None = "69aa91735931"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("distractor", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("traps", sa.JSON(), nullable=True))
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("probe", sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_column("probe")
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_column("traps")
        batch_op.drop_column("distractor")
