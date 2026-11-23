"""Content pack versions on attempts and decisions (src/flashtap/learners/models.py `content`): the packs each round
drew from, {pack: version}, so a rebuild or replay can tell a round made from packs since changed (spec §14, "record
generator seed, source versions").

Existing rows are filled in, not left empty: every pack has been at version 1 since the packs were written (`git log
-p src/flashtap/packs` shows no other `version =` line), so the packs each kind drew from are known exactly. The table
below is what `rounds.content_of` gave for each kind when this migration was written, copied rather than imported so
the migration means the same thing whatever the packs say later. A decision without a round (a break or an end) keeps
None.

Revision ID: ad08d3806978
Revises: 8611114c2acc
Create Date: 2026-11-23 17:54:01.962229

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad08d3806978"
down_revision: str | Sequence[str] | None = "8611114c2acc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEXICON = {"phonics.letters_and_sounds": 1, "words": 1}  # every kind counts the words and phonics packs
_SKILLS: dict[str, tuple[str, ...]] = {  # and the packs of the skills it names
    "matching": ("language",),
    "colours": ("language",),
    "shapes": ("language", "maths.number"),
    "letters": ("language", "literacy.early"),
    "counting": ("maths.number",),
    "missing": ("maths.number",),
    "quick_look": ("maths.number",),
    "listen": ("literacy.early",),
    "give": ("maths.number",),
    "order": ("maths.number",),
    "capitals": ("literacy.early",),
    "sort_sounds": ("language", "literacy.early"),
}
CONTENT: dict[str, dict[str, int]] = {mode: {**_LEXICON, **dict.fromkeys(packs, 1)} for mode, packs in _SKILLS.items()}


def _fill(table: str, rounds_only: bool) -> None:
    t = sa.table(table, sa.column("mode", sa.String()), sa.column("content", sa.JSON()))
    for mode, content in CONTENT.items():
        op.execute(t.update().where(t.c.mode == mode).values(content=content))
    if not rounds_only:
        # A kind not in the table cannot be in the log (these are all the kinds there have been); were one there, an
        # empty map is read as "not recorded" and rebuilt from the packs as they are, as an export from before this is.
        op.execute(t.update().where(t.c.content.is_(None)).values(content={}))


def upgrade() -> None:
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("content", sa.JSON(), nullable=True))
    _fill("attempts", rounds_only=False)
    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.alter_column("content", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("content", sa.JSON(), nullable=True))
    _fill("decisions", rounds_only=True)  # a break or an end has no mode and keeps None


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_column("content")

    with op.batch_alter_table("attempts", schema=None) as batch_op:
        batch_op.drop_column("content")
