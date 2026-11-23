"""The engine's sessions on the learner records (spec §15): start one, ask for its next decision, replay a learner's.

`POST /api/v1/sessions` starts a session with a snapshot of the settings it will run with. `POST .../next {seq}` asks
for decision number `seq` (0, 1, 2 ...): the first time it is made, logged and returned; asked again (a retry after a
lost answer, a reload) the logged one comes back unchanged, so a decision is never made twice and its round is never
swapped for another. Asking past the next number is refused, as is asking after the session has ended.

A decision is made from the learner's whole log as the server has it (`replay.as_of` at the decision's time, the same
function a replay uses), so remaking it later from the log gives the same choice.
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
from flashtap.engine.policy import POLICY, Action, Candidate, Config, Logged, Why, decide, explain
from flashtap.engine.replay import as_of, past_of, replay
from flashtap.learners import store
from flashtap.learners.models import Decision, Sitting, utc
from flashtap.learners.store import Conflict, IdText, now
from flashtap.mechanics import Round


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
    rounds_played: int  # rounds chosen in this session before this decision
    candidates: list[Candidate]


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


def _out(d: Logged, earlier: list[Logged], config: Config, titles: dict[str, str]) -> Next:
    played = sum(1 for x in earlier if x.action is Action.ROUND and x.seq < d.seq)
    r = None
    if d.action is Action.ROUND and d.mode is not None and d.choices is not None:
        r = rounds.generate(d.mode, d.choices, d.seed, d.version, d.content)
        r.tries = rounds.tries_allowed(config.tries, r)
    return Next(
        id=d.id,
        session_id=d.session_id,
        seq=d.seq,
        at=d.at,
        policy=d.policy,
        action=d.action,
        round=r,
        skill=d.skill,
        skill_title=titles.get(d.skill) if d.skill else None,
        rationale=d.rationale,
        why=explain(d, titles, config, played),
        probability=d.probability,
        rounds_played=played,
        candidates=d.candidates,
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
        fold(as_of(log, when), g),
        past_of(started, made, log, session_id, when, seq),
        config,
        f"{session_id}:{seq}",
        when,
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
            content=c.content,
            skill=c.skill,
            rationale=[w.value for w in c.rationale],
            probability=c.probability,
            candidates=[x.model_dump(mode="json") for x in c.candidates],
        )
    )
    db.commit()  # the unique (session, seq) backs up the lock
    return _out(d, [*made, d], config, titles)


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
    if body.policy != POLICY.id:
        raise ValueError(f"Only the current policy, {POLICY.id}, is kept; {body.policy} cannot be replayed.")
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
    same, diffs = replay(log, made, sittings, g)
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
