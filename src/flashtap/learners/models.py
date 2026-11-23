"""The learner records (plan PR 4; the spec's §14 event store): who plays, when, and every round they answered.

Five tables in the app's schema (strata_python.db; migrations in `src/flashtap/migrations/`):

- `learners`: a pseudonymous id (random, means nothing outside this database) and a nickname chosen by the grown-up.
  Nothing else: no age, birth date, year group, school or photo (AGENTS.md rule 8, spec §17). What comes next is
  decided by evidence of ability, so nothing here could be used to gate by age.
- `sessions`: one sitting, named by the browser (a fresh id each time Play opens for a learner), so attempts sent
  later, or twice, still land in the right one (§14: the client queues, the server reconciles idempotently).
- `attempts`: append-only, one row per round answered, keyed by the browser's `event_id`. A row stores what is needed
  to rebuild the round (kind, version, choices, seed, and the version of each content pack it drew from) and the
  skills it gave evidence on *as they were when it was played*, so a later change to a template or a pack cannot
  rewrite a learner's history. Only the first answer is judged
  (§10: retries are teaching, not independent evidence); the number of tries and how the round ended are kept beside
  it for the engagement work later (P4).
- `decisions`: what the adaptive engine chose for a session, and why (plan PR 5; the class below says more).
- `tombstones`: an attempt struck out by a grown-up ("someone else was playing") and why. The attempt stays, so the
  log is still append-only; every estimate skips struck attempts.

Deleting a learner deletes their rows in every table (`ON DELETE CASCADE`; §17 export and delete). Nothing here keeps
derived state: estimates are computed from the attempts on every read (`report.py`), so they are rebuilt from the
event log by construction, which is the PR's exit criterion.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, ForeignKey, Index, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from strata_python.db import NAMING_CONVENTION

ID_LENGTH = 36  # a UUID as text, the longest id the browser sends; ours are 32 hex digits
NICKNAME_LENGTH = 40


class Base(MappedAsDataclass, DeclarativeBase):  # written out, not make_base(): ty cannot subclass a returned type
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSON,
        dict[str, int]: JSON,
        list[dict[str, str]]: JSON,
        list[dict[str, Any]]: JSON,
        list[str]: JSON,
    }


def utc(at: datetime) -> datetime:
    """`at` as an aware UTC time. SQLite hands back the naive UTC time it was given; Postgres an aware one."""
    return at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC)


class Learner(Base):
    __tablename__ = "learners"
    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(NICKNAME_LENGTH))
    created_at: Mapped[datetime]


class Sitting(Base):
    """A session (§14). Named Sitting here because SQLAlchemy's own Session is everywhere beside it."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime]  # when the engine started it, or else the earliest attempt's presented_at
    last_at: Mapped[datetime]  # the latest attempt's answered_at
    # Set for a session the adaptive engine plans (POST /api/v1/sessions): its policy and the settings it started
    # with (engine/policy.py `Config`), so every decision in it replays with the same. None for one the browser named.
    policy: Mapped[str | None] = mapped_column(String(32), default=None)
    config: Mapped[dict[str, Any] | None] = mapped_column(default=None)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_learner_id_presented_at", "learner_id", "presented_at"),)

    event_id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    # The round: (mode, version, choices, seed, content) rebuilds it exactly (rounds.generate). `content` is the
    # content packs it drew from, {pack: version}: a word or sound changed in a pack changes the round a seed gives,
    # so without it a rebuild after a pack's version is raised would show, and judge, a round nobody saw.
    mode: Mapped[str] = mapped_column(String(32))
    version: Mapped[int]
    choices: Mapped[int]
    seed: Mapped[int]
    content: Mapped[dict[str, int]]
    mechanic: Mapped[str] = mapped_column(String(32))
    options: Mapped[int]  # how many tiles a one-tap round offered (its chance of a lucky tap); 0 for a placing round
    skills: Mapped[list[dict[str, str]]]  # [{"skill": id, "role": primary|secondary|confound}] as played
    asked: Mapped[str] = mapped_column(String(32))  # what the grown-up picked ("mixed", or the kind itself): the policy
    presented_at: Mapped[datetime]
    answered_at: Mapped[datetime]  # the first answer
    first_answer: Mapped[dict[str, Any]]  # {"option": id} or {"placement": {piece: place}}
    first_correct: Mapped[bool]  # judged by the server from the rebuilt round, never taken from the browser
    tries: Mapped[int]  # taps or checks used, the first included
    outcome: Mapped[str] = mapped_column(String(16))  # right, missed (ran out of tries) or left (moved on unanswered)
    received_at: Mapped[datetime]
    # The engine's decision this round answered (None when the grown-up chose the kind). Not a foreign key: a
    # decision and its attempt are deleted together with their learner, and the store checks it matches on the way in.
    decision_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), default=None, index=True)


class Decision(Base):
    """One decision of the adaptive engine (spec §12, §14): what it chose and why, every candidate it weighed with
    its utility and its chance of being picked, and the policy that made it. Append-only, like the attempts: a
    replay (engine/replay.py) remakes each one from the log as it stood and compares."""

    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("session_id", "seq"),)

    id: Mapped[str] = mapped_column(String(ID_LENGTH), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    seq: Mapped[int]  # 0, 1, 2 ... within the session: the browser asks for the next by number, so a retry is safe
    at: Mapped[datetime]
    policy: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16))  # round, break or end
    mode: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int | None]
    choices: Mapped[int | None]
    seed: Mapped[int | None]
    content: Mapped[dict[str, int] | None]  # the round's content packs and versions, as on its attempt; None: no round
    skill: Mapped[str | None] = mapped_column(String(80))
    rationale: Mapped[list[str]]
    probability: Mapped[float]
    candidates: Mapped[list[dict[str, Any]]]


class Tombstone(Base):
    __tablename__ = "tombstones"
    event_id: Mapped[str] = mapped_column(ForeignKey("attempts.event_id", ondelete="CASCADE"), primary_key=True)
    reason: Mapped[str] = mapped_column(String(200))
    at: Mapped[datetime]
