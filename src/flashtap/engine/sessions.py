"""The engine's sessions on the learner records (spec §15): start one, ask for its next decision, replay a learner's.

`POST /api/v1/sessions` starts a session with a snapshot of the settings it will run with. `POST .../next {seq}` asks
for decision number `seq` (0, 1, 2 ...): the first time it is made, logged and returned; asked again (a retry after a
lost answer, a reload) the logged one comes back unchanged, so a decision is never made twice and its round is never
swapped for another. Asking past the next number is refused, as is asking after the session has ended.

A decision is made from the learner's whole log as the server has it (`replay.as_of` at the decision's time, the same
function a replay uses), the grown-ups' overrides standing then and the learner's preferences then (their ratings and
earlier picks), so remaking it later from the log gives the same choice.

A choice between two activities (`Action.CHOICE`) is answered by the learner: `POST .../decisions/{seq}/pick {offer}`
records which, once (the same pick again is acknowledged, another refused), and only while it is still the session's
latest decision, so the next decision and a replay of it see the same pick. The round played is then the picked offer.
"""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flashtap import rounds
from flashtap.engine import simulate
from flashtap.engine.evaluate import Score, scores
from flashtap.engine.model import Graph, fold
from flashtap.engine.policy import POLICY, REPLAYS, Action, Candidate, Config, Logged, Offer, Why, decide, explain
from flashtap.engine.replay import as_of, likes_as_of, past_of, replay
from flashtap.learners import store
from flashtap.learners.evidence import told_as_of
from flashtap.learners.models import Decision, Sitting, utc
from flashtap.learners.store import Conflict, IdText, now
from flashtap.mechanics import Mode, Round


class SessionIn(BaseModel):
    learner_id: str = IdText


class SessionInfo(BaseModel):
    """`POST /api/v1/sessions`: the session, the policy that will plan it and the settings it runs with."""

    id: str
    learner_id: str
    policy: str
    config: Config
    started_at: datetime


class NextIn(BaseModel):
    seq: int = Field(ge=0, le=10_000)


class OfferOut(BaseModel):
    """One of a choice's two rounds, ready to play once picked, with its picture and name for the learner."""

    mode: Mode
    title: str  # the kind's name, said aloud: "Counting"
    picture: str
    skill: str
    skill_title: str
    round: Round
    why: str


class PickIn(BaseModel):
    offer: int = Field(ge=0, le=1)


class Next(BaseModel):
    """`POST /api/v1/sessions/{id}/next`: a round to play (`round`, checked, with its tries), an offered break, or the
    end of the session, with the rationale codes, the same in words for a grown-up, and what else was weighed."""

    id: str
    session_id: str
    seq: int
    at: datetime
    policy: str
    action: Action
    round: Round | None
    skill: str | None
    skill_title: str | None
    rationale: list[Why]
    why: str
    probability: float
    rounds_played: int  # rounds played in this session before this decision
    candidates: list[Candidate]
    offers: list[OfferOut] | None = None  # a choice's two rounds; `round` is the picked one's once picked
    picked: int | None = None
    rate: bool = False  # ask how the round was (three faces) once it is over


def start(db: Session, learner_id: str, config: Config, at: datetime | None = None) -> SessionInfo:
    store.get_learner(db, learner_id)
    when = at or now()
    x = Sitting(
        id=uuid.uuid4().hex,
        learner_id=learner_id,
        started_at=when,
        last_at=when,
        policy=POLICY.id,
        config=config.model_dump(),
    )
    db.add(x)
    db.commit()
    return SessionInfo(id=x.id, learner_id=learner_id, policy=POLICY.id, config=config, started_at=when)


def _sitting(db: Session, session_id: str) -> tuple[Sitting, Config]:
    x = db.get(Sitting, session_id)
    if x is None or x.policy is None or x.config is None:
        raise KeyError(f"No engine session {session_id}: start one with POST /api/v1/sessions.")
    return x, Config.model_validate(x.config)


def _logged(db: Session, session_id: str) -> list[Logged]:
    return [
        store.logged(d)
        for d in db.scalars(select(Decision).where(Decision.session_id == session_id).order_by(Decision.seq))
    ]


def _round(o: Offer, config: Config) -> Round:
    r = rounds.generate(o.mode, o.choices, o.seed, o.version, o.content, o.level)
    r.tries = rounds.tries_allowed(config.tries, r)
    return r


def _out(d: Logged, earlier: list[Logged], config: Config, titles: dict[str, str]) -> Next:
    played = sum(1 for x in earlier if x.played() is not None and x.seq < d.seq)
    r = None
    if d.action is Action.ROUND and d.mode is not None and d.choices is not None:
        r = rounds.generate(d.mode, d.choices, d.seed, d.version, d.content, d.level)
        r.tries = rounds.tries_allowed(config.tries, r)
    offers = None
    if d.action is Action.CHOICE and d.offers is not None:
        offers = [
            OfferOut(
                mode=o.mode,
                title=rounds.MODE_NAMES[o.mode][0],
                picture=rounds.PICTURES[o.mode],
                skill=o.skill,
                skill_title=titles.get(o.skill, o.skill),
                round=_round(o, config),
                why=explain(d.model_copy(update={"rationale": []}), titles, config, played, i),
            )
            for i, o in enumerate(d.offers)
        ]
        if d.picked is not None:
            r = offers[d.picked].round
    skill = o.skill if (o := d.offered(d.picked)) is not None else d.skill
    return Next(
        id=d.id,
        session_id=d.session_id,
        seq=d.seq,
        at=d.at,
        policy=d.policy,
        action=d.action,
        round=r,
        skill=skill,
        skill_title=titles.get(skill) if skill else None,
        rationale=d.rationale,
        why=explain(d, titles, config, played, d.picked),
        probability=d.probability,
        rounds_played=played,
        candidates=d.candidates,
        offers=offers,
        picked=d.picked,
        rate=d.rate,
    )


def next_decision(
    db: Session, session_id: str, seq: int, g: Graph, titles: dict[str, str], at: datetime | None = None
) -> Next:
    sitting, config = _sitting(db, session_id)
    # The learner's lock before the read and the clock: attempts and strikes take it before stamping their time, so
    # the log read here is exactly the log `as_of(when)` rebuilds in a replay, and two requests for one number queue
    # (the second then finds the first's decision).
    store.hold(db, sitting.learner_id)
    made = _logged(db, session_id)
    if seq < len(made):
        db.rollback()
        return _out(made[seq], made, config, titles)
    if made and made[-1].action is Action.END:
        db.rollback()
        raise Conflict("This session has ended: start a new one.")
    if seq != len(made):
        raise ValueError(f"The next decision in this session is number {len(made)}, not {seq}.")
    when = at or now()
    log = store.events(db, sitting.learner_id)
    started = utc(sitting.started_at)
    c = decide(
        fold(as_of(log, when), g, told=told_as_of(store.told(db, sitting.learner_id), when)),
        past_of(started, made, log, session_id, when, seq),
        config,
        f"{session_id}:{seq}",
        when,
        likes=likes_as_of(store.ratings(db, sitting.learner_id), store.decisions(db, sitting.learner_id), when),
    )
    d = Logged(id=uuid.uuid4().hex, session_id=session_id, seq=seq, at=when, **c.model_dump())
    db.add(
        Decision(
            id=d.id,
            learner_id=sitting.learner_id,
            session_id=session_id,
            seq=seq,
            at=when,
            policy=c.policy,
            action=c.action.value,
            mode=c.mode.value if c.mode else None,
            version=c.version,
            choices=c.choices,
            seed=c.seed,
            level=c.level,
            probe=c.probe,
            content=c.content,
            skill=c.skill,
            rationale=[w.value for w in c.rationale],
            probability=c.probability,
            candidates=[x.model_dump(mode="json") for x in c.candidates],
            offers=[o.model_dump(mode="json") for o in c.offers] if c.offers is not None else None,
            rate=c.rate,
        )
    )
    db.commit()  # the unique (session, seq) backs up the lock
    return _out(d, [*made, d], config, titles)


def pick(
    db: Session, session_id: str, seq: int, offer: int, titles: dict[str, str], at: datetime | None = None
) -> Next:
    """The learner's pick of offer `offer` in choice `seq`: recorded once, and only while it is the latest decision."""
    sitting, config = _sitting(db, session_id)
    store.hold(db, sitting.learner_id)  # picks change what later decisions see, so they queue with them
    x = db.scalar(select(Decision).where(Decision.session_id == session_id, Decision.seq == seq))
    if x is None or x.action != Action.CHOICE.value or not x.offers:
        db.rollback()
        raise KeyError(f"No choice {seq} in session {session_id}.")
    if x.picked is not None:
        db.rollback()
        if x.picked != offer:
            raise Conflict(f"Choice {seq} was already answered with offer {x.picked}; a pick is never changed.")
    else:
        later = db.scalar(
            select(func.count()).select_from(Decision).where(Decision.session_id == session_id, Decision.seq > seq)
        )
        if later:
            db.rollback()
            raise Conflict(f"The session has moved on past choice {seq}: it can no longer be picked from.")
        x.picked = offer
        x.picked_at = at or now()
        db.commit()
    made = _logged(db, session_id)
    return _out(made[seq], made, config, titles)


class SimulatedIn(BaseModel):
    learners: int = Field(default=40, ge=4, le=200)
    sessions: int = Field(default=6, ge=1, le=20)
    seed: int = Field(default=1, ge=0)


class ReplayIn(BaseModel):
    """`POST /api/v1/evaluations/replay`: the policy to replay with (only the current one is kept) and the data, one of
    a learner's records or a simulation."""

    policy: str = POLICY.id
    learner_id: str | None = None
    simulated: SimulatedIn | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.learner_id is None) == (self.simulated is None):
            raise ValueError("replay needs a learner_id or a simulated dataset, not both")
        return self


class ReplayOut(BaseModel):
    policy: str
    dataset: str
    decisions: int  # logged decisions remade
    reproduced: int  # of which identical
    differences: list[str]
    scores: list[Score]  # how well each model predicted each first answer from the ones before it; best first
    simulation: simulate.SimReport | None


def evaluate(db: Session, body: ReplayIn, g: Graph) -> ReplayOut:
    if body.policy not in REPLAYS:
        kept = ", ".join(sorted(REPLAYS))
        raise ValueError(f"Only {kept} can be replayed; {body.policy} is not kept.")
    if body.simulated is not None:
        s = body.simulated
        rep = simulate.report(s.learners, s.sessions, s.seed, g)
        return ReplayOut(
            policy=POLICY.id,
            dataset=f"simulated: {s.learners} learners, {s.sessions} sessions, seed {s.seed}",
            decisions=0,
            reproduced=0,
            differences=[],
            scores=rep.scores,
            simulation=rep,
        )
    learner = body.learner_id or ""
    store.get_learner(db, learner)
    log = store.events(db, learner)
    made = store.decisions(db, learner)
    sittings = {x.id: (x.started_at, x.config) for x in store.sessions_of(db, learner)}
    same, diffs = replay(log, made, sittings, g, store.ratings(db, learner), store.told(db, learner))
    n = db.scalar(select(func.count()).select_from(Decision).where(Decision.learner_id == learner)) or 0
    return ReplayOut(
        policy=POLICY.id,
        dataset=f"learner {learner}",
        decisions=n,
        reproduced=same,
        differences=diffs,
        scores=scores([log], g),
        simulation=None,
    )
