"""Reading and writing the learner records: learners, attempts (idempotent by event_id), tombstones, ratings, a
grown-up's overrides, export and delete.

The server judges every attempt itself: the browser sends the round's (mode, version, choices, seed, content) and the
first answer, and the round is rebuilt here to decide whether that answer was right (the spec's rule that the server
owns the truth). An attempt on a round made from packs the server no longer has (a pack's version was raised between
the round being served and answered) is refused rather than judged against today's round, which may be another. A browser that sends the same attempt twice (a retry after a lost answer, or a queue replayed) gets the
same acknowledgement; one that sends a different attempt under a used event_id is refused (409), since an event, once
logged, is never rewritten (§14).
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Literal, Self, cast

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from strata_python.tasks.flight import Conflict as FlightConflict

from flashtap import __version__, mistakes, rounds
from flashtap.engine.policy import Action, Candidate, Config, Logged, Offer, Why
from flashtap.learners import engagement, misconceptions
from flashtap.learners.engagement import Engagement, Offered, Rated
from flashtap.learners.evidence import Event, Observer, Says, SkillUse, Told
from flashtap.learners.misconceptions import MisconceptionReport
from flashtap.learners.models import (
    ID_LENGTH,
    NICKNAME_LENGTH,
    Attempt,
    Decision,
    Learner,
    Override,
    Rating,
    Sitting,
    Tombstone,
    utc,
)
from flashtap.learners.report import (
    MODELS,
    ModelInfo,
    SkillInfo,
    SkillReport,
    differences,
    known_misconceptions,
    skill_reports,
)
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
    db.execute(delete(Rating).where(Rating.learner_id == learner_id))
    db.execute(delete(Override).where(Override.learner_id == learner_id))
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
    level: int | None = Field(default=None, ge=0)  # the round's step of difficulty as served; None: no step (by hand)
    # The round's `content` as served: the packs it drew from and their versions. Sent back so the server judges the
    # round that was shown; None (a browser from before 0.7.0, or a queue it left) is judged against the packs as
    # they are now, which is what that browser was served unless a pack changed in between.
    content: dict[str, int] | None = None
    # Who chose the kind: the grown-up (mixed, or the kind itself), the engine (next), or the device (offline: the
    # engine could not be reached, so the round came from those the device kept of the kinds it had chosen that visit).
    asked: Mode | Literal["next", "offline"]
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
    # ValueError (400) for a template version or pack version no longer kept
    r = rounds.generate(a.mode, a.choices, a.seed, a.version, a.content, a.level)
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
    tapped = next((o for o in r.options if o.id == a.first_answer.option), None)  # None for a placing round
    return Attempt(
        event_id=a.event_id,
        learner_id=a.learner_id,
        session_id=a.session_id,
        mode=r.mode.value,
        version=r.version,
        choices=r.choices,
        seed=r.seed,
        level=r.level,
        content=r.content,
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
        distractor=tapped.distractor if tapped is not None else None,
        traps=mistakes.traps(r) if tapped is not None else None,
    )


def _same(old: Attempt, a: AttemptIn) -> bool:
    """Whether `a` is the attempt already logged as `old`, compared with what the browser sent rather than with a
    round rebuilt now: a retry of an attempt logged before a pack changed is still the same attempt."""
    sent = (
        a.learner_id,
        a.session_id,
        a.mode.value,
        a.version,
        a.choices,
        a.seed,
        a.level,
        str(a.asked),
        a.first_answer.model_dump(exclude_none=True),
        a.tries,
        a.outcome,
        a.decision_id,
    )
    kept = (
        old.learner_id,
        old.session_id,
        old.mode,
        old.version,
        old.choices,
        old.seed,
        old.level,
        old.asked,
        old.first_answer,
        old.tries,
        old.outcome,
        old.decision_id,
    )
    return (
        sent == kept
        and (a.content is None or a.content == old.content)
        and (utc(old.presented_at), utc(old.answered_at)) == (a.presented_at, a.answered_at)
    )


def hold(db: Session, learner_id: str) -> None:
    """Take the learner's row lock until this transaction ends, before reading the clock for a receipt, a strike or an
    engine decision. Those three are then serialised per learner, so a time stamped under the lock orders them as the
    database saw them: an attempt stamped before a decision was committed before the decision read the log, and one
    stamped after waited for it. Without it, an attempt stamped first but committed after a decision's read would be
    missing from the decision and present in its replay (engine/replay.py `as_of`). A no-op UPDATE locks the row on
    Postgres and takes SQLite's write lock."""
    db.execute(update(Learner).where(Learner.id == learner_id).values(nickname=Learner.nickname))


def record(db: Session, a: AttemptIn, at: datetime | None = None) -> Ack:
    get_learner(db, a.learner_id)
    if a.mode is Mode.MIXED:
        raise ValueError("mode is the kind played; a mixed round reports its own kind")
    if a.asked == "offline" and a.decision_id is not None:
        raise ValueError("a round the device chose offline answers no engine decision")
    hold(db, a.learner_id)
    # A duplicate first, before the round is rebuilt: the packs may have moved on since it was logged.
    old = db.get(Attempt, a.event_id)
    if old is not None:
        if not _same(old, a):
            raise Conflict(
                f"Event {a.event_id} is already logged with different contents; an event is never rewritten."
            )
        db.rollback()  # nothing to write: let the lock go
        return Ack(event_id=a.event_id, first_correct=old.first_correct, duplicate=True)
    r, right = _judge(a)
    row = _row(a, r, right, at or now())
    if a.decision_id is not None:
        _check_decision(db, a, r)
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


def _check_decision(db: Session, a: AttemptIn, r: rounds.Round) -> None:
    """An attempt that names a decision answers the round that decision chose, in its session, once."""
    d = db.get(Decision, a.decision_id)
    if d is None or d.learner_id != a.learner_id or d.session_id != a.session_id:
        raise ValueError(f"No decision {a.decision_id} in session {a.session_id} for this learner.")
    chosen = (d.action, d.mode, d.version, d.choices, d.seed, d.content, d.level)
    if d.action == "choice":  # the round is the offer the learner picked
        o = logged(d).offered(d.picked)
        if o is None:
            raise ValueError(f"Decision {a.decision_id} is a choice nobody has picked from yet.")
        chosen = ("round", o.mode.value, o.version, o.choices, o.seed, o.content, o.level)
    if chosen != ("round", r.mode.value, r.version, r.choices, r.seed, r.content, r.level):
        raise ValueError(f"Decision {a.decision_id} chose a different round.")
    other = db.scalar(select(Attempt.event_id).where(Attempt.decision_id == a.decision_id))
    if other is not None:
        raise Conflict(f"Decision {a.decision_id} was already answered by event {other}.")


def strike(db: Session, event_id: str, reason: str, at: datetime | None = None) -> None:
    """Strike an attempt out of every estimate (a tombstone; the attempt itself stays in the log). Striking twice keeps
    the first reason."""
    x = db.get(Attempt, event_id)
    if x is None:
        raise KeyError(f"No attempt {event_id}.")
    reason = " ".join(reason.split())[:200] or "struck out by a grown-up"
    hold(db, x.learner_id)
    if db.get(Tombstone, event_id) is None:
        db.add(Tombstone(event_id=event_id, reason=reason, at=at or now()))
    db.commit()


# Ratings


class RatingIn(BaseModel):
    """`POST /api/attempts/{event_id}/rating`: how the learner said the round was, on three faces."""

    value: Literal[-1, 0, 1]
    scale: engagement.Scale = "enjoyment"


class RatingAck(BaseModel):
    event_id: str
    scale: engagement.Scale
    value: int
    duplicate: bool


def rate(db: Session, event_id: str, body: RatingIn, at: datetime | None = None) -> RatingAck:
    """Keep a rating of a recorded round: once per round and scale. Sent again with the same face it is
    acknowledged; with another it is refused (409), as an attempt is: a log entry is never rewritten."""
    x = db.get(Attempt, event_id)
    if x is None:
        raise KeyError(f"No attempt {event_id}: a round is rated once it is recorded.")
    hold(db, x.learner_id)
    old = db.get(Rating, (event_id, body.scale))
    if old is not None:
        db.rollback()
        if old.value != body.value:
            raise Conflict(f"Round {event_id} is already rated {old.value}; a rating is never rewritten.")
        return RatingAck(event_id=event_id, scale=body.scale, value=old.value, duplicate=True)
    db.add(Rating(event_id=event_id, scale=body.scale, learner_id=x.learner_id, value=body.value, at=at or now()))
    db.commit()
    return RatingAck(event_id=event_id, scale=body.scale, value=body.value, duplicate=False)


def ratings(db: Session, learner_id: str) -> list[Rated]:
    q = (
        select(Rating, Attempt.session_id, Attempt.mode)
        .join(Attempt, Attempt.event_id == Rating.event_id)
        .where(Rating.learner_id == learner_id)
        .order_by(Rating.at, Rating.event_id)
    )
    return [
        Rated(
            event_id=r.event_id,
            session_id=sid,
            mode=mode,
            scale=cast("engagement.Scale", r.scale),
            value=r.value,
            at=utc(r.at),
        )
        for r, sid, mode in db.execute(q).all()
    ]


# Overrides


class OverrideIn(BaseModel):
    """`POST /api/v1/learners/{id}/overrides`: a grown-up's observation of one skill (spec §15 "scoped human
    observation"): the skill is its scope, `observer` its source label."""

    skill: str = Field(min_length=1, max_length=80)
    says: Says
    observer: Observer
    note: str = Field(default="", max_length=200)


def told(db: Session, learner_id: str) -> list[Told]:
    """Every override for the learner, withdrawn ones too, oldest first."""
    q = select(Override).where(Override.learner_id == learner_id).order_by(Override.at, Override.id)
    return [
        Told(
            id=x.id,
            skill=x.skill,
            says=cast("Says", x.says),
            observer=cast("Observer", x.observer),
            note=x.note,
            at=utc(x.at),
            withdrawn_at=utc(x.withdrawn_at) if x.withdrawn_at is not None else None,
        )
        for x in db.scalars(q)
    ]


def tell(db: Session, learner_id: str, body: OverrideIn, skills: set[str], at: datetime | None = None) -> Told:
    get_learner(db, learner_id)
    if body.skill not in skills:
        raise ValueError(f"No skill {body.skill} in the content packs.")
    note = " ".join(body.note.split())
    hold(db, learner_id)  # stamped under the lock, as attempts are, so a replay knows which decisions saw it
    x = Override(
        id=uuid.uuid4().hex,
        learner_id=learner_id,
        skill=body.skill,
        says=body.says,
        observer=body.observer,
        note=note,
        at=at or now(),
    )
    db.add(x)
    db.commit()
    return next(t for t in told(db, learner_id) if t.id == x.id)


def withdraw(db: Session, learner_id: str, override_id: str, at: datetime | None = None) -> None:
    """Stop an override counting from now. Withdrawing twice keeps the first time."""
    hold(db, learner_id)
    # Read under the lock, fresh from the database: a copy read before it could miss a withdrawal committed meanwhile
    # and overwrite its time, which would change what a decision made between the two saw on replay.
    x = db.get(Override, override_id, populate_existing=True)
    if x is None or x.learner_id != learner_id:
        db.rollback()
        raise KeyError(f"No override {override_id} for this learner.")
    if x.withdrawn_at is None:
        x.withdrawn_at = at or now()
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
            level=x.level,
            content=x.content,
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
            distractor=x.distractor,
            traps=x.traps,
        )
        for x, reason, struck_at in db.execute(q).all()
    ]


# The running score


class RunningScore(BaseModel):
    """`GET /api/learners/{id}/score`: every round the learner has answered, ever, by whether the first answer was
    right. All time, not per session: the number a child sees grow. Struck rounds are left out (a grown-up said they
    were not the learner's answer), and so are rounds never answered, which are never recorded."""

    right: int
    wrong: int


def score(db: Session, learner_id: str) -> RunningScore:
    get_learner(db, learner_id)
    # Counted in the database, not from `events`: the score is read on every visit to Play, and the log grows forever.
    q = (
        select(Attempt.first_correct, func.count())
        .outerjoin(Tombstone, Tombstone.event_id == Attempt.event_id)
        .where(Attempt.learner_id == learner_id, Tombstone.event_id.is_(None))
        .group_by(Attempt.first_correct)
    )
    counts = {bool(right): n for right, n in db.execute(q)}
    return RunningScore(right=counts.get(True, 0), wrong=counts.get(False, 0))


# Reports


class Profile(BaseModel):
    """`GET /api/learners/{id}/profile`: the learner, what was recorded and every skill's estimates and state."""

    learner: LearnerRow
    sessions: int
    struck: int
    models: list[ModelInfo]
    skills: list[SkillReport]
    misconceptions: list[MisconceptionReport]  # every one a round has offered them, suspected first
    engagement: Engagement


def offered(made: list[Logged]) -> list[Offered]:
    """Every choice between two activities in the learner's decisions."""
    out: list[Offered] = []
    for d in made:
        if d.action is Action.CHOICE and d.offers is not None and len(d.offers) == 2:
            o = d.offered(d.picked)
            out.append(
                Offered(
                    first=d.offers[0].mode.value,
                    second=d.offers[1].mode.value,
                    picked=o.mode.value if o is not None else None,
                    at=d.picked_at,
                )
            )
    return out


def profile(
    db: Session,
    learner_id: str,
    skills: list[SkillInfo],
    log: list[Event] | None = None,
    said: list[Told] | None = None,
    rated: list[Rated] | None = None,
    made: list[Logged] | None = None,
) -> Profile:
    log = events(db, learner_id) if log is None else log
    said = told(db, learner_id) if said is None else said
    rated = ratings(db, learner_id) if rated is None else rated
    made = decisions(db, learner_id) if made is None else made
    names = {m.value: n for m, (n, _) in rounds.MODE_NAMES.items()}
    return Profile(
        learner=learner_row(db, learner_id),
        sessions=db.scalar(select(func.count()).select_from(Sitting).where(Sitting.learner_id == learner_id)) or 0,
        struck=sum(e.struck is not None for e in log),
        models=MODELS,
        skills=skill_reports(log, skills, said),
        misconceptions=misconceptions.report(log, known_misconceptions()),
        engagement=engagement.report(log, rated, offered(made), names),
    )


class SessionOut(BaseModel):
    id: str
    started_at: datetime
    last_at: datetime
    policy: str | None = None  # an engine session's policy and settings (absent before 0.6.0)
    config: Config | None = None


class Export(BaseModel):
    """Everything held about one learner (§17), and the estimates made from it, so a rebuild can be checked."""

    # @2 (0.6.0) adds the engine's decisions and each session's policy; @3 (0.7.0) each attempt's and decision's
    # content packs; @4 (0.8.0) ratings, a grown-up's overrides, and choices with their picks; @5 (0.11.0) each
    # attempt's and decision's step of difficulty; @6 (0.12.0) each attempt's distractor and traps, each decision's
    # probe, and each skill's fluency and suspected misconceptions; @7 (0.13.0) each skill's transfer evidence, and
    # generalised read from it. Older files still read, with none of what they lack.
    format: Literal[
        "flashtap-learner@1",
        "flashtap-learner@2",
        "flashtap-learner@3",
        "flashtap-learner@4",
        "flashtap-learner@5",
        "flashtap-learner@6",
        "flashtap-learner@7",
    ] = "flashtap-learner@7"
    exported_at: datetime
    app_version: str
    learner: LearnerRow
    sessions: list[SessionOut]
    events: list[Event]
    decisions: list[Logged] = Field(default_factory=list[Logged])
    ratings: list[Rated] = Field(default_factory=list[Rated])
    overrides: list[Told] = Field(default_factory=list[Told])
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
        level=x.level,
        probe=x.probe,
        content=x.content,
        skill=x.skill,
        rationale=[Why(w) for w in x.rationale],
        probability=x.probability,
        candidates=[Candidate.model_validate(c) for c in x.candidates],
        offers=[Offer.model_validate(o) for o in x.offers] if x.offers is not None else None,
        rate=x.rate,
        picked=x.picked,
        picked_at=utc(x.picked_at) if x.picked_at is not None else None,
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
    log, said, rated, made = (
        events(db, learner_id),
        told(db, learner_id),
        ratings(db, learner_id),
        decisions(db, learner_id),
    )
    p = profile(db, learner_id, skills, log, said, rated, made)
    return Export(
        exported_at=at or now(),
        app_version=__version__,
        learner=p.learner,
        sessions=sessions_of(db, learner_id),
        events=log,
        decisions=made,
        ratings=rated,
        overrides=said,
        models=p.models,
        skills=p.skills,
    )


# The export format each per-skill field was first recorded in: an older export read today gets the field's default,
# which is not what the log rebuilds to, so a rebuild leaves it out rather than calling it a difference. The rules of
# a field it did record are compared as they are now: a state read by a rule since changed (Generalised, 0.13.0) is
# reported, as it is a real difference.
ADDED: dict[str, int] = {"told": 4, "fluency": 6, "suspected": 6, "transfer": 7}


def rebuild(saved: Export, skills: list[SkillInfo] | None = None) -> list[str]:
    """Rebuild the estimates from an export's events and say where they differ from the ones it carries (none: the
    log reproduces them exactly). `skills` defaults to the skills the export reported on, so an export from an older
    pack still compares like with like."""
    known = (
        skills
        if skills is not None
        else [SkillInfo(id=s.skill, title=s.title, domain=s.domain, strand=s.strand) for s in saved.skills]
    )
    at = int(saved.format.rsplit("@", 1)[1])
    absent = frozenset(f for f, since in ADDED.items() if at < since)
    return differences(saved.skills, skill_reports(saved.events, known, saved.overrides), absent)
