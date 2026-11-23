"""The scheduler (spec §12): what a learner plays next, and why.

Each call looks at the learner's knowledge (`model.Knowledge`, folded from their whole log) and at this session so far,
and returns one decision: a round, an offered break, or the end of the session.

1. **Limits first, never traded** (§12: "constrain frustration and session duration rather than trading them"): the
   session ends at `Config.max_rounds` rounds or `max_minutes` minutes; a break is offered every `break_every` rounds
   and after `FRUSTRATED` first answers missed in a row.
2. **Candidates**: one per kind of round, aimed at the skill it is written to assess (its primary). Each is labelled
   with what it would do for that skill: a `placement_probe` while the learner has little evidence, `introduce` for a
   skill with none, `practise` until BKT's estimate reaches `MASTERED`, `spaced_review` once a mastered skill's recall
   has faded below `DUE`, else `consolidate`.
3. **Eligibility**: a candidate is set aside (and logged with why) when a strong prerequisite has evidence of not being
   known yet (`prerequisite_gap`), when two misses in a row make it a likely third (`frustration_guard`), or when it was
   the last two rounds (`just_played`).
4. **Utility**, the spec's sum: expected learning (how far from known, times how ready its prerequisites are),
   information (the entropy of the predicted answer, weighted up during placement and by how many unseen skills the
   graph would place from it), retention need, enjoyment (a success chance near three in four, and a change of
   mechanic), minus frustration risk and recent repetition, plus a diagnostic bonus for a contrast after a miss (below).
5. **Seeded exploration**: a softmax over the utilities at temperature `tau`, mixed with `epsilon` of a uniform pick so
   every eligible candidate has a known, non-zero chance. The draw comes from a generator seeded by the session and the
   decision's number, so a replay makes the same pick, and every candidate is logged with its components and its
   probability, which is what an unbiased offline evaluation of another policy needs (§14).

**Diagnostic contrasts** (§12): after a missed round, a candidate that shares a skill with it but leaves out another
(Missing number after Counting: the numerals without the counting) isolates a cause; it gets a bonus for how uncertain
the shared skills still are, and the rationale says so. A frustrated learner gets a break first, never more diagnosis.

Every number here is a starting point, logged with the decision so a replay or a fit later can change them openly.
"""

import bisect
import itertools
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from flashtap import rounds
from flashtap.engine.model import SHAPES, Knowledge, RoundShape
from flashtap.mechanics import SEED_LIMIT, Mode

MASTERED = 0.85  # BKT's estimate at which practice turns to review; the Learner screen's "independent" threshold
DUE = 0.5  # recall below which a mastered skill is brought back
PLACING = 12  # counted answers, over every skill, before placement probes give way to teaching
FRUSTRATED = 3  # first answers missed in a row that end in an offered break
GUARDED = 2  # misses in a row after which only rounds likely to go right are offered


class Action(StrEnum):
    ROUND = "round"
    BREAK = "break"
    END = "end"


class Why(StrEnum):
    """Rationale codes (§15 "validated item + rationale codes"): what a decision is for."""

    PLACEMENT = "placement_probe"
    INTRODUCE = "introduce"
    PRACTISE = "practise"
    REVIEW = "spaced_review"
    CONSOLIDATE = "consolidate"
    CONTRAST = "diagnostic_contrast"
    EASIER = "easier_after_misses"
    EXPLORE = "exploration"
    BREAK_DUE = "break_due"
    FRUSTRATION = "frustration_break"
    CAP_ROUNDS = "session_cap_rounds"
    CAP_MINUTES = "session_cap_minutes"


class SetAside(StrEnum):
    PREREQUISITE = "prerequisite_gap"
    FRUSTRATION = "frustration_guard"
    REPEAT = "just_played"


class Config(BaseModel):
    """A session's settings, snapshotted when it starts (§15 "consent/config snapshot"), so a replay uses the same."""

    choices: int = Field(ge=2, le=8)
    tries: int = Field(ge=0)
    max_rounds: int = Field(default=20, ge=1)
    max_minutes: int = Field(default=15, ge=1)
    break_every: int = Field(default=10, ge=1)


class Candidate(BaseModel):
    mode: Mode
    skill: str  # the primary skill it would give evidence on
    action: Why
    contrast: bool
    p_right: float
    learning: float
    information: float
    retention: float
    enjoyment: float
    frustration: float
    repetition: float
    diagnostic: float
    utility: float
    probability: float  # of being picked; 0 when set aside
    set_aside: SetAside | None


class Choice(BaseModel):
    """One decision as the policy made it: what is logged, what a replay must reproduce."""

    policy: str
    action: Action
    mode: Mode | None = None
    version: int | None = None
    content: dict[str, int] | None = None  # the packs the round draws from, as its attempt will record them
    choices: int | None = None
    seed: int | None = None
    skill: str | None = None
    rationale: list[Why]
    probability: float  # of this pick: 1 for a break or an end, which are rules, not draws
    candidates: list[Candidate] = Field(default_factory=list[Candidate])


class Logged(Choice):
    """A decision as stored and exported: the choice, where it was made and when."""

    id: str
    session_id: str
    seq: int
    at: datetime


@dataclass(frozen=True)
class Past:
    """The session so far, oldest first: its start, each decision's action and kind, each attempt's first answer and
    kind. Attempts, not decisions, say what was missed: a round can be left unanswered."""

    started: datetime
    decisions: Sequence[tuple[Action, Mode | None]] = ()
    answers: Sequence[tuple[Mode, bool]] = ()

    def rounds(self) -> list[Mode]:
        return [m for a, m in self.decisions if a is Action.ROUND and m is not None]

    def since_break(self) -> int:
        n = 0
        for a, _ in reversed(self.decisions):
            if a is Action.BREAK:
                break
            n += a is Action.ROUND
        return n

    def misses(self) -> int:
        n = 0
        for _, right in reversed(self.answers):
            if right:
                break
            n += 1
        return n


@dataclass(frozen=True)
class Weights:
    learning: float = (
        2.0  # 1.0 learnt less than a uniform pick on simulated learners; 2.0 more, at a similar success rate
    )
    information: float = 0.8
    placing: float = 2.0  # information counts this many times more while placing
    reach: float = 0.15  # and this much more per unseen skill the graph would place from the answer
    retention: float = 0.8
    enjoyment: float = 0.3
    frustration: float = 0.6
    repetition: float = 0.8
    diagnostic: float = 0.6


@dataclass(frozen=True)
class Policy:
    name: str = "utility"
    version: int = 1
    weights: Weights = field(default_factory=Weights)
    tau: float = 0.15  # softmax temperature: lower picks the best more often
    epsilon: float = 0.1  # share of every pick that is uniform over the eligible candidates

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"


POLICY = Policy()


def entropy(p: float) -> float:
    """Binary entropy in bits: 1 at an even chance, 0 when the answer is certain."""
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def decide(k: Knowledge, past: Past, config: Config, key: str, now: datetime, policy: Policy = POLICY) -> Choice:
    """The next decision for a session. `key` seeds the draw (the session id and the decision's number), so the same
    knowledge, session, config, key and time always give the same decision."""
    played = past.rounds()
    if len(played) >= config.max_rounds:
        return Choice(policy=policy.id, action=Action.END, rationale=[Why.CAP_ROUNDS], probability=1.0)
    if (now - past.started).total_seconds() >= config.max_minutes * 60:
        return Choice(policy=policy.id, action=Action.END, rationale=[Why.CAP_MINUTES], probability=1.0)
    misses = past.misses()
    just_broke = bool(past.decisions) and past.decisions[-1][0] is Action.BREAK
    if not just_broke and misses >= FRUSTRATED and past.since_break() >= FRUSTRATED:
        return Choice(policy=policy.id, action=Action.BREAK, rationale=[Why.FRUSTRATION], probability=1.0)
    if not just_broke and past.since_break() >= config.break_every:
        return Choice(policy=policy.id, action=Action.BREAK, rationale=[Why.BREAK_DUE], probability=1.0)

    failed = past.answers[-1][0] if past.answers and not past.answers[-1][1] else None
    cands = [_candidate(k, s, past, config, now, policy, misses, failed) for s in SHAPES]
    open_ = [c for c in cands if c.set_aside is None]
    if not open_:  # never stuck: drop the softer filters first, the prerequisite gap last
        open_ = [c for c in cands if c.set_aside is not SetAside.PREREQUISITE] or cands
    best = max(c.utility for c in open_)
    weights = [math.exp((c.utility - best) / policy.tau) for c in open_]
    total = sum(weights)
    probs = {
        id(c): (1 - policy.epsilon) * w / total + policy.epsilon / len(open_)
        for c, w in zip(open_, weights, strict=True)
    }
    logged = [c.model_copy(update={"probability": probs.get(id(c), 0.0)}) for c in cands]
    pool = [c for c in logged if c.probability > 0]

    rng = random.Random(key)
    draw, seed = rng.random(), rng.randrange(SEED_LIMIT)
    # The first candidate whose running total passes the draw; the last when rounding leaves the total a hair under 1.
    pick = pool[min(bisect.bisect_right(list(itertools.accumulate(c.probability for c in pool)), draw), len(pool) - 1)]
    why = [pick.action]
    if pick.contrast:
        why.append(Why.CONTRAST)
    if misses >= GUARDED:
        why.append(Why.EASIER)
    if pick.utility < max(c.utility for c in pool):
        why.append(Why.EXPLORE)
    shape = next(s for s in SHAPES if s.mode is pick.mode)
    return Choice(
        policy=policy.id,
        action=Action.ROUND,
        mode=pick.mode,
        version=shape.version,
        content=rounds.content_of(pick.mode),
        choices=config.choices,
        seed=seed,
        skill=pick.skill,
        rationale=why,
        probability=pick.probability,
        candidates=logged,
    )


def _candidate(
    k: Knowledge,
    shape: RoundShape,
    past: Past,
    config: Config,
    now: datetime,
    policy: Policy,
    misses: int,
    failed: Mode | None,
) -> Candidate:
    w = policy.weights
    g = k.graph
    me = k.state(shape.primary)
    placing = k.counted < PLACING
    if me.own == 0:
        action = Why.PLACEMENT if placing else Why.INTRODUCE
    elif me.p < MASTERED:
        action = Why.PRACTISE
    elif me.recall(now) < DUE:
        action = Why.REVIEW
    else:
        action = Why.CONSOLIDATE

    p_right = k.p_right(shape.skills, shape.options(config.choices))
    before = g.before.get(shape.primary, frozenset())
    ready = min((k.p(q) for q in before), default=1.0)
    learning = (1 - me.p) * ready
    reach = sum(1 for s in before | g.after.get(shape.primary, frozenset()) if k.state(s).own == 0)
    information = entropy(p_right) * (1 + w.reach * reach) * (w.placing if placing else 1.0)
    retention = 1 - me.recall(now) if me.own and me.p >= MASTERED else 0.0
    rounds = past.rounds()
    switch = 1.0 if rounds and next(s for s in SHAPES if s.mode is rounds[-1]).mechanic is not shape.mechanic else 0.0
    enjoyment = 0.7 * max(0.0, 1 - abs(p_right - 0.75) / 0.75) + 0.3 * switch
    frustration = (1 - p_right) * (1 + misses)
    recent = rounds[-4:]
    repetition = sum(m is shape.mode for m in recent) / 4

    contrast, diagnostic = False, 0.0
    if failed is not None and failed is not shape.mode:
        lost = next(s for s in SHAPES if s.mode is failed)
        shared = set(shape.skills) & set(lost.skills)
        if shared and set(lost.skills) - set(shape.skills):
            contrast = True
            diagnostic = sum(entropy(k.p(s)) for s in shared) / len(shared)

    set_aside: SetAside | None = None
    if any(k.state(q).own >= 2 and k.p(q) < 0.3 for q in before):
        set_aside = SetAside.PREREQUISITE
    elif misses >= GUARDED and p_right < 0.6:
        set_aside = SetAside.FRUSTRATION
    elif rounds[-2:] == [shape.mode, shape.mode]:
        set_aside = SetAside.REPEAT

    utility = (
        w.learning * learning
        + w.information * information
        + w.retention * retention
        + w.enjoyment * enjoyment
        - w.frustration * frustration
        - w.repetition * repetition
        + w.diagnostic * diagnostic
    )
    return Candidate(
        mode=shape.mode,
        skill=shape.primary,
        action=action,
        contrast=contrast,
        p_right=round(p_right, 6),
        learning=round(learning, 6),
        information=round(information, 6),
        retention=round(retention, 6),
        enjoyment=round(enjoyment, 6),
        frustration=round(frustration, 6),
        repetition=round(repetition, 6),
        diagnostic=round(diagnostic, 6),
        utility=round(utility, 6),
        probability=0.0,
        set_aside=set_aside,
    )


_SAY: dict[Why, str] = {
    Why.PLACEMENT: "Finding where to start, a first look at: {skill}.",
    Why.INTRODUCE: "Something new: {skill}.",
    Why.PRACTISE: "Practising: {skill}.",
    Why.REVIEW: "Back for review, so it is not forgotten: {skill}.",
    Why.CONSOLIDATE: "Keeping it going: {skill}.",
    Why.CONTRAST: "It leaves out part of the last round, to see which part was hard.",
    Why.EASIER: "One likely to go right, after a few misses.",
    Why.EXPLORE: "Not the top pick: a few are chosen by chance, so the plan keeps learning.",
    Why.BREAK_DUE: "{rounds} played so far.",
    Why.FRUSTRATION: "A break, after a few misses in a row.",
    Why.CAP_ROUNDS: "A session is {rounds} at most.",
    Why.CAP_MINUTES: "A session is {minutes} minutes at most.",
}


def explain(c: Choice, titles: Mapping[str, str], config: Config, rounds_played: int) -> str:
    """The rationale in words, for the grown-up (the codes stay in the log)."""
    skill = titles.get(c.skill or "", c.skill or "")
    played = f"{rounds_played} round" + ("" if rounds_played == 1 else "s")
    return " ".join(_SAY[w].format(skill=skill, rounds=played, minutes=config.max_minutes) for w in c.rationale)
