"""Steps of difficulty (0.11.0; src/flashtap/rounds.py `Level`): a `level` column on `attempts` and on `decisions`, the
step of difficulty the engine chose for the round, which with (mode, version, choices, seed, content) rebuilds it.

Nullable with no default: every existing attempt and decision was made without a step (the grown-up's number of
choices and the kind's fixed range), which is exactly what None means, so they rebuild and replay unchanged.

Revision ID: 69aa91735931
Revises: e6f732116499
Create Date: 2026-11-24 06:50:45.677126

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "69aa91735931"
down_revision: str | Sequence[str] | None = "e6f732116499"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("level", sa.Integer(), nullable=True))
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("level", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_column("level")
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_column("level")
