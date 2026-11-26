"""The job queue's table (0.14.0; strata_python.tasks.queue `jobs_table`, `flashtap.jobs`): what the server does on its
own, such as making the voice's clips. A new table: nothing before it changes.

Revision ID: c6263d1db252
Revises: 937000175eca
Create Date: 2026-11-26 06:22:28.386570

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6263d1db252"
down_revision: str | Sequence[str] | None = "937000175eca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=500), nullable=True),
        sa.Column("options", sa.Text(), nullable=False),
        sa.Column("dedupe", sa.String(length=64), nullable=True),
        sa.Column("resources", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.Float(), nullable=True),
        sa.Column("timeout_s", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("finished_at", sa.Float(), nullable=True),
        sa.Column("heartbeat_at", sa.Float(), nullable=True),
        sa.Column("owner", sa.String(length=200), nullable=True),
        sa.Column("owner_pid", sa.Integer(), nullable=True),
        sa.Column("claim_token", sa.String(length=32), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("progress", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index("ix_jobs_claim", ["state", "priority", "id"], unique=False)
        batch_op.create_index("ix_jobs_dedupe", ["dedupe"], unique=False)
        batch_op.create_index("ix_jobs_domain", ["domain"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_domain")
        batch_op.drop_index("ix_jobs_dedupe")
        batch_op.drop_index("ix_jobs_claim")

    op.drop_table("jobs")
