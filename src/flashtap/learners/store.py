"""Reading and writing the learner records: learners, attempts (idempotent by event_id), tombstones, export and delete.

The server judges every attempt itself: the browser sends the round's (mode, version, choices, seed) and the first
answer, and the round is rebuilt here to decide whether that answer was right (the spec's rule that the server owns
the truth). A browser that sends the same attempt twice (a retry after a lost answer, or a queue replayed) gets the
same acknowledgement; one that sends a different attempt under a used event_id is refused (409), since an event, once
logged, is never rewritten (§14).
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Literal, Self, cast

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from strata_python.tasks.flight import Conflict as FlightConflict

from flashtap import __version__, rounds
from flashtap.engine.policy import Action, Candidate, Config, Logged, Why
from flashtap.learners.evidence import Event, SkillUse
from flashtap.learners.models import ID_LENGTH, NICKNAME_LENGTH, Attempt, Decision, Learner, Sitting, Tombstone, utc
from flashtap.learners.report import MODELS, ModelInfo, SkillInfo, SkillReport, differences, skill_reports
from flashtap.mechanics import PLACE, SEED_LIMIT, Mode, arranged_right

IdText = Field(pattern=rf"^[0-9a-fA-F-]{{8,{ID_LENGTH}}}$")  # a UUID, with or without its dashes
IdOrNone = Field(default=None, pattern=rf"^[0-9a-fA-F-]{{8,{ID_LENGTH}}}$")


class Conflict(FlightConflict):
    """A write that would contradict what is stored (answered 409, through strata_python.web's error map)."""


def now() -> datetime:
    return datetime.now(UTC)


# Learners


class LearnerRow(BaseModel):
    id: str
    nickname: str
    created_at: datetime
    attempts: int  # rounds recorded, struck ones included
    last_played: datetime | None


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def nickname_of(text: str) -> str:
    """A nickname as stored: trimmed, 1 to 40 characters, one line."""
    name = " ".join(text.split())
    if not name:
        raise ValueError("A nickname needs at least one letter.")
    if len(name) > NICKNAME_LENGTH or _CONTROL.search(name):
        raise ValueError(f"A nickname is one line of at most {NICKNAME_LENGTH} characters.")
    return name


def _taken(db: Session, name: str, other_than: str | None = None) -> None:
    for lid, nick in db.execute(select(Learner.id, Learner.nickname)):
        if nick.casefold() == name.casefold() and lid != other_than:
            raise Conflict(f"There is already a learner called {nick}.")


def list_learners(db: Session) -> list[LearnerRow]:
    stats = {
        lid: (n, last)
        for lid, n, last in db.execute(
            select(Attempt.learner_id, func.count(), func.max(Attempt.presented_at)).group_by(Attempt.learner_id)
        )
    }
    return [
        LearnerRow(
            id=x.id,
            nickname=x.nickname,
            created_at=utc(x.created_at),
            attempts=stats.get(x.id, (0, None))[0],
            last_played=utc(last) if (last := stats.get(x.id, (0, None))[1]) else None,
        )
        for x in db.scalars(select(Learner).order_by(Learner.nickname))
    ]


def get_learner(db: Session, learner_id: str) -> Learner:
    x = db.get(Learner, learner_id)
    if x is None:
        raise KeyError(f"No learner {learner_id}: removed, or never added.")
    return x


def learner_row(db: Session, learner_id: str) -> LearnerRow:
    get_learner(db, learner_id)
    return next(r for r in list_learners(db) if r.id == learner_id)


def add_learner(db: Session, nickname: str, at: datetime | None = None) -> LearnerRow:
    name = nickname_of(nickname)
    _taken(db, name)
    x = Learner(id=uuid.uuid4().hex, nickname=name, created_at=at or now())
    db.add(x)
    db.commit()
    return learner_row(db, x.id)


def rename_learner(db: Session, learner_id: str, nickname: str) -> LearnerRow:
    x = get_learner(db, learner_id)
    name = nickname_of(nickname)
    _taken(db, name, other_than=learner_id)
    x.nickname = name
    db.commit()
    return learner_row(db, learner_id)


def delete_learner(db: Session, learner_id: str) -> None:
    """The learner and everything recorded about them (sessions, attempts, tombstones), at once and for good (§17).
    Deleted explicitly, child rows first, rather than trusting ON DELETE CASCADE alone: the cascade is there too, but a
    SQLite connection without foreign keys on would silently leave the attempts behind."""
    get_learner(db, learner_id)
    attempts = select(Attempt.event_id).where(Attempt.learner_id == learner_id)
    db.execute(delete(Tombstone).where(Tombstone.event_id.in_(attempts)))
    db.execute(delete(Attempt).where(Attempt.learner_id == learner_id))
    db.execute(delete(Decision).where(Decision.learner_id == learner_id))
    db.execute(delete(Sitting).where(Sitting.learner_id == learner_id))
    db.execute(delete(Learner).where(Learner.id == learner_id))
    db.commit()


# Attempts


class FirstAnswer(BaseModel):
    """The first answer given: one option's id (a one-tap round), or where each piece was at the first check."""

    option: str | None = None
    placement: dict[str, str] | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.option is None) == (self.placement is None):
            raise ValueError("first_answer needs an option or a placement, not both")
        return self


class AttemptIn(BaseModel):
    """`POST /api/attempts`: one round answered, sent once the round is over (or left)."""

    event_id: str = IdText
    learner_id: str = IdText
    session_id: str = IdText
    mode: Mode  # the kind played (never mixed)
    version: int = Field(ge=1)
    choices: int = Field(ge=rounds.MIN_CHOICES, le=rounds.MAX_CHOICES)
    seed: int = Field(ge=0, lt=SEED_LIMIT)
    asked: Mode | Literal["next"]  # the kind the grown-up picked: mixed, the kind itself, or next (the engine chose)
    presented_at: AwareDatetime
    answered_at: AwareDatetime
    first_answer: FirstAnswer
    tries: int = Field(ge=1, le=100)
    outcome: Literal["right", "missed", "left"]
    decision_id: str | None = IdOrNone  # the engine's decision this round answers (POST /api/v1/sessions/{id}/next)


class Ack(BaseModel):
    event_id: str
    first_correct: bool
    duplicate: bool  # this event was already logged; nothing changed


def _judge(a: AttemptIn) -> tuple[rounds.Round, bool]:
    if a.mode is Mode.MIXED:
        raise ValueError("mode is the kind played; a mixed round reports its own kind")
    r = rounds.generate(a.mode, a.choices, a.seed, a.version)  # ValueError (400) for a version no longer kept
    ans = a.first_answer
    if r.mechanic in PLACE:
        if ans.placement is None:
            raise ValueError("a placing round is answered with a placement")
        pieces, places = {p.id for p in r.pieces}, {s.id for s in r.places}
        if not set(ans.placement) <= pieces or not set(ans.placement.values()) <= places:
            raise ValueError("the placement names a piece or place this round does not have")
        right = arranged_right(r, ans.placement)
    else:
        if ans.option is None or ans.option not in {o.id for o in r.options}:
            raise ValueError("the first answer is not one of this round's options")
        right = ans.option == r.answer
    if right and (a.tries != 1 or a.outcome != "right"):
        raise ValueError("the first answer was right, so the round ended there: one try, outcome right")
    if not right and a.outcome == "right" and a.tries < 2:
        raise ValueError("the first answer was wrong, so a right outcome took more than one try")
    if a.answered_at < a.presented_at:
        raise ValueError("answered_at is before presented_at")
    return r, right


def _row(a: AttemptIn, r: rounds.Round, right: bool, received: datetime) -> Attempt:
    return Attempt(
        event_id=a.event_id,
        learner_id=a.learner_id,
        session_id=a.session_id,
        mode=r.mode.value,
        version=r.version,
        choices=r.choices,
        seed=r.seed,
        mechanic=r.mechanic.value,
        options=0 if r.mechanic in PLACE else len(r.options),
        skills=[{"skill": s.skill, "role": s.role.value} for s in r.skills],
        asked=str(a.asked),  # a Mode is a StrEnum: its value
        presented_at=a.presented_at.astimezone(UTC),
        answered_at=a.answered_at.astimezone(UTC),
        first_answer=a.first_answer.model_dump(exclude_none=True),
        first_correct=right,
        tries=a.tries,
        outcome=a.outcome,
        received_at=received,
        decision_id=a.decision_id,
    )


_SAME = (
    "learner_id",
    "session_id",
    "mode",
    "version",
    "choices",
    "seed",
    "asked",
    "first_answer",
    "tries",
    "outcome",
    "decision_id",
)


def _same(old: Attempt, new: Attempt) -> bool:
    return all(getattr(old, f) == getattr(new, f) for f in _SAME) and all(
        utc(getattr(old, f)) == utc(getattr(new, f)) for f in ("presented_at", "answered_at")
    )


def record(db: Session, a: AttemptIn, at: datetime | None = None) -> Ack:
    get_learner(db, a.learner_id)
    r, right = _judge(a)
    row = _row(a, r, right, at or now())
    old = db.get(Attempt, a.event_id)
    if old is not None:
        if not _same(old, row):
            raise Conflict(
                f"Event {a.event_id} is already logged with different contents; an event is never rewritten."
            )
        return Ack(event_id=a.event_id, first_correct=old.first_correct, duplicate=True)
    if a.decision_id is not None:
        _check_decision(db, a)
    sitting = db.get(Sitting, a.session_id)
    if sitting is None:
        db.add(Sitting(id=a.session_id, learner_id=a.learner_id, started_at=row.presented_at, last_at=row.answered_at))
        db.flush()  # the session first: with no relationship() between them, the ORM does not order the two inserts
    elif sitting.learner_id != a.learner_id:
        raise Conflict(f"Session {a.session_id} belongs to another learner.")
    else:
        if sitting.policy is None:  # an engine session keeps the start it was given: its time limit counts from there
            sitting.started_at = min(utc(sitting.started_at), row.presented_at)
        sitting.last_at = max(utc(sitting.last_at), row.answered_at)
    db.add(row)
    db.commit()
    return Ack(event_id=a.event_id, first_correct=right, duplicate=False)


def _check_decision(db: Session, a: AttemptIn) -> None:
    """An attempt that names a decision answers the round that decision chose, in its session, once."""
    d = db.get(Decision, a.decision_id)
    if d is None or d.learner_id != a.learner_id or d.session_id != a.session_id:
        raise ValueError(f"No decision {a.decision_id} in session {a.session_id} for this learner.")
    if (d.action, d.mode, d.version, d.choices, d.seed) != ("round", a.mode.value, a.version, a.choices, a.seed):
        raise ValueError(f"Decision {a.decision_id} chose a different round.")
    other = db.scalar(select(Attempt.event_id).where(Attempt.decision_id == a.decision_id))
    if other is not None:
        raise Conflict(f"Decision {a.decision_id} was already answered by event {other}.")


def strike(db: Session, event_id: str, reason: str, at: datetime | None = None) -> None:
    """Strike an attempt out of every estimate (a tombstone; the attempt itself stays in the log). Striking twice keeps
    the first reason."""
    if db.get(Attempt, event_id) is None:
        raise KeyError(f"No attempt {event_id}.")
    reason = " ".join(reason.split())[:200] or "struck out by a grown-up"
    if db.get(Tombstone, event_id) is None:
        db.add(Tombstone(event_id=event_id, reason=reason, at=at or now()))
        db.commit()


def events(db: Session, learner_id: str) -> list[Event]:
    """The learner's log, oldest first, each attempt with its tombstone's reason when struck."""
    q = (
        select(Attempt, Tombstone.reason, Tombstone.at)
        .outerjoin(Tombstone, Tombstone.event_id == Attempt.event_id)
        .where(Attempt.learner_id == learner_id)
        .order_by(Attempt.presented_at, Attempt.event_id)
    )
    return [
        Event(
            event_id=x.event_id,
            session_id=x.session_id,
            mode=x.mode,
            version=x.version,
            choices=x.choices,
            seed=x.seed,
            mechanic=x.mechanic,
            options=x.options,
            skills=[SkillUse(skill=s["skill"], role=s["role"]) for s in x.skills],
            asked=x.asked,
            presented_at=utc(x.presented_at),
            answered_at=utc(x.answered_at),
            first_answer=x.first_answer,
            first_correct=x.first_correct,
            tries=x.tries,
            outcome=x.outcome,
            struck=reason,
            received_at=utc(x.received_at),
            struck_at=utc(at) if (at := cast("datetime | None", struck_at)) is not None else None,  # None: not struck
            decision_id=x.decision_id,
        )
        for x, reason, struck_at in db.execute(q).all()
    ]


# Reports


class Profile(BaseModel):
    """`GET /api/learners/{id}/profile`: the learner, what was recorded and every skill's estimates and state."""

    learner: LearnerRow
    sessions: int
    struck: int
    models: list[ModelInfo]
    skills: list[SkillReport]


def profile(db: Session, learner_id: str, skills: list[SkillInfo], log: list[Event] | None = None) -> Profile:
    log = events(db, learner_id) if log is None else log
    return Profile(
        learner=learner_row(db, learner_id),
        sessions=db.scalar(select(func.count()).select_from(Sitting).where(Sitting.learner_id == learner_id)) or 0,
        struck=sum(e.struck is not None for e in log),
        models=MODELS,
        skills=skill_reports(log, skills),
    )


class SessionOut(BaseModel):
    id: str
    started_at: datetime
    last_at: datetime
    policy: str | None = None  # an engine session's policy and settings (absent before 0.6.0)
    config: Config | None = None


class Export(BaseModel):
    """Everything held about one learner (§17), and the estimates made from it, so a rebuild can be checked."""

    # @2 (0.6.0) adds the engine's decisions and each session's policy; an @1 file still reads, with none of either.
    format: Literal["flashtap-learner@1", "flashtap-learner@2"] = "flashtap-learner@2"
    exported_at: datetime
    app_version: str
    learner: LearnerRow
    sessions: list[SessionOut]
    events: list[Event]
    decisions: list[Logged] = Field(default_factory=list[Logged])
    models: list[ModelInfo]
    skills: list[SkillReport]


def sessions_of(db: Session, learner_id: str) -> list[SessionOut]:
    rows = db.scalars(select(Sitting).where(Sitting.learner_id == learner_id).order_by(Sitting.started_at, Sitting.id))
    return [
        SessionOut(
            id=x.id,
            started_at=utc(x.started_at),
            last_at=utc(x.last_at),
            policy=x.policy,
            config=Config.model_validate(x.config) if x.config is not None else None,
        )
        for x in rows
    ]


def logged(x: Decision) -> Logged:
    return Logged(
        id=x.id,
        session_id=x.session_id,
        seq=x.seq,
        at=utc(x.at),
        policy=x.policy,
        action=Action(x.action),
        mode=Mode(x.mode) if x.mode is not None else None,
        version=x.version,
        choices=x.choices,
        seed=x.seed,
        skill=x.skill,
        rationale=[Why(w) for w in x.rationale],
        probability=x.probability,
        candidates=[Candidate.model_validate(c) for c in x.candidates],
    )


def decisions(db: Session, learner_id: str) -> list[Logged]:
    q = (
        select(Decision)
        .where(Decision.learner_id == learner_id)
        .order_by(Decision.at, Decision.session_id, Decision.seq)
    )
    return [logged(x) for x in db.scalars(q)]


def export(db: Session, learner_id: str, skills: list[SkillInfo], at: datetime | None = None) -> Export:
    # One read of the log for both the events and the estimates: a second read could see a round recorded or
    # struck in between (READ COMMITTED), and the export would then not rebuild to its own estimates.
    log = events(db, learner_id)
    p = profile(db, learner_id, skills, log)
    return Export(
        exported_at=at or now(),
        app_version=__version__,
        learner=p.learner,
        sessions=sessions_of(db, learner_id),
        events=log,
        decisions=decisions(db, learner_id),
        models=p.models,
        skills=p.skills,
    )


def rebuild(saved: Export, skills: list[SkillInfo] | None = None) -> list[str]:
    """Rebuild the estimates from an export's events and say where they differ from the ones it carries (none: the
    log reproduces them exactly). `skills` defaults to the skills the export reported on, so an export from an older
    pack still compares like with like."""
    known = (
        skills
        if skills is not None
        else [SkillInfo(id=s.skill, title=s.title, domain=s.domain, strand=s.strand) for s in saved.skills]
    )
    return differences(saved.skills, skill_reports(saved.events, known))
