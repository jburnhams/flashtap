"""The scheduler (spec §12): what a learner plays next, and why.

Each call looks at the learner's knowledge (`model.Knowledge`, folded from their whole log and any grown-up's
overrides), what they have said they like (`likes`, engagement.preferences) and at this session so far, and returns
one decision: a round, a choice between two rounds for the learner to pick, an offered break, or the end of the session.

1. **Limits first, never traded** (§12: "constrain frustration and session duration rather than trading them"): the
   session ends at `Config.max_rounds` rounds or `max_minutes` minutes; a break is offered every `break_every` rounds
   (0: never) and after `FRUSTRATED` first answers missed in a row, whatever the settings say. The grown-up sets the
   first three (Settings, Sessions); the frustration break is not theirs to turn off.
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
   mechanic, and what they have said they like: `liked`, a kind's preference from -1 to 1), minus frustration risk and
   recent repetition, plus a diagnostic bonus for a contrast after a miss (below). A preference only nudges: it is
   weighed with enjoyment, under the same limits, and never outweighs a prerequisite gap or the frustration guard.
5. **Seeded exploration**: a softmax over the utilities at temperature `tau`, mixed with `epsilon` of a uniform pick so
   every eligible candidate has a known, non-zero chance. The draw comes from a generator seeded by the session and the
   decision's number, so a replay makes the same pick, and every candidate is logged with its components and its
   probability, which is what an unbiased offline evaluation of another policy needs (§14).
6. **A choice of two** (§12 "offer choice", P4): every `choice_every` rounds (0: never) the decision is a choice
   instead of a round: the drawn candidate and the open candidate with the best utility among the other mechanics (or,
   with only one mechanic open, the other kinds), shown to the learner side by side. Which one they pick is theirs,
   recorded on the decision (`sessions.pick`) and read back as a preference. The logged probability is the draw's: the
   second offer follows from the first.
7. **Asking how it was**: a decision whose round is the `rate_every`th of the session (0: never) says `rate`, and
   Play shows the three faces after it. Optional: Next works without a face.

8. **Steps of difficulty** (§6, from `utility@4`): each candidate is made at the step its kind's stair has reached
   (`model.Stair`), one step easier after `GUARDED` misses in a row, and the round lays out that step's number of
   choices. A kind with no stair yet starts at the easiest step, or halfway up when its skill is already known
   (`MASTERED`, from the learner's own answers, the graph or a grown-up), so a learner who can already do it is not
   walked up from the bottom (§13 "rapid acceleration"). The step decides the chance of a lucky answer in `p_right`.
   The grown-up's number of choices (`Config.choices`) is for the rounds they pick by hand and for decisions of
   `utility@3` and before, which replay with it.

9. **Checking a misconception** (§16 "misconception discrimination", from `utility@5`): a misconception the learner's
   wrong taps have shown and not since cleared (`Knowledge.mistakes`, `learners/misconceptions.py`) gives a bonus to
   each kind of round that can offer its trap at the step it would be played at (`mistakes.PROBES`): more while
   suspected, half while it could still be luck. A candidate checks one at a time, the suspected first. Picked, its
   round's seed is the first of `PROBE_TRIES` drawn from a generator of its own (the decision's key and the kind) whose
   round does offer the trap, so the draw that picked it and the seeds after it are the same as without a probe, and a
   replay finds the same seed. If none does, the round is played without one and the rationale does not claim it. The
   frustration guard still comes first: a probe is a round that could go wrong.

10. **Transfer probes** (§12 "transfer probe", §13 "progress when ... transfer probes pass", from `utility@6`): a
   transfer kind (`rounds.HELD_OUT`, a second form of one skill) is held out of practice. Its candidate is set aside
   (`held_out`) unless its skill is rated known (`MASTERED`) with at least `CHECK_AFTER` right answers of its own in
   the practice kinds and has not passed its check yet (`learners/transfer.py`: the latest two transfer answers
   right); then it is a `transfer_probe`, with a bonus (`Weights.transfer`) for what passing would tell, and every
   other term as usual, so the frustration guard and the limits still come first. A check that is missed stays open
   and comes back after more practice like any other candidate. The never-stuck fallback never opens a held-out kind.
   `utility@5` and before do not weigh the transfer kinds at all, and still replay.

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

from flashtap import content, mistakes, rounds
from flashtap.engine.model import SHAPES, Knowledge, RoundShape
from flashtap.learners.misconceptions import MisconceptionStatus as Status
from flashtap.mechanics import SEED_LIMIT, Mode

MASTERED = 0.85  # BKT's estimate at which practice turns to review; the Learner screen's "independent" threshold
DUE = 0.5  # recall below which a mastered skill is brought back
PLACING = 12  # counted answers, over every skill, before placement probes give way to teaching
FRUSTRATED = 3  # first answers missed in a row that end in an offered break
GUARDED = 2  # misses in a row after which only rounds likely to go right are offered
CHECK_AFTER = 3  # right answers in its practice kinds before a known skill is checked in its transfer kind
PROBE_TRIES = 100  # seeds tried for a round that offers a misconception's trap (the rarest, in Sounds, is 1 in 14)


class Action(StrEnum):
    ROUND = "round"
    CHOICE = "choice"
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
    OFFER = "offered_choice"
    LIKED = "liked"  # what they said they like moved it up
    STEP_UP = "step_up"  # a step harder than their last round of this kind
    STEP_DOWN = "step_down"  # a step easier than their last round of this kind
    PROBE = "misconception_probe"  # it offers the tap a misconception they may have predicts (utility@5 on)
    TRANSFER = "transfer_probe"  # a known skill asked in its second, held-out form (utility@6 on)


class SetAside(StrEnum):
    PREREQUISITE = "prerequisite_gap"
    FRUSTRATION = "frustration_guard"
    REPEAT = "just_played"
    HELD_OUT = "held_out"  # a transfer kind whose skill is not due a check (utility@6 on)


class Config(BaseModel):
    """A session's settings, snapshotted when it starts (§15 "consent/config snapshot"), so a replay uses the same."""

    choices: int = Field(ge=2, le=8)
    tries: int = Field(ge=0)
    max_rounds: int = Field(default=20, ge=1)
    max_minutes: int = Field(default=15, ge=1)
    break_every: int = Field(default=10, ge=0)  # 0: no regular breaks (the frustration break stays)
    # 0, not the settings' defaults, so a session snapshotted before 0.8.0 (which has neither) replays as it ran.
    choice_every: int = Field(default=0, ge=0)
    rate_every: int = Field(default=0, ge=0)


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
    liked: float = 0.0  # the kind's preference, -1 to 1 (absent from decisions before 0.8.0, which had none)
    level: int | None = None  # the step it would be played at (None before utility@4: the grown-up's choices)
    stepped: int = 0  # 1 a step harder than their last round of this kind, -1 easier, 0 the same or none before
    probe: str | None = None  # the misconception it would check (utility@5 on); None: none, or before
    misconception: float = 0.0  # the bonus for checking it: 1 suspected, 0.5 unclear
    utility: float
    probability: float  # of being picked; 0 when set aside
    set_aside: SetAside | None


class Offer(BaseModel):
    """One of the two rounds a choice offers: enough to rebuild it, and why it was put forward."""

    mode: Mode
    version: int
    content: dict[str, int]
    choices: int
    seed: int
    skill: str
    rationale: list[Why]
    level: int | None = None  # the step of difficulty (utility@4 on); with the five above it rebuilds the round
    probe: str | None = None  # the misconception its round offers the trap of, when picked to check it (utility@5)


class Choice(BaseModel):
    """One decision as the policy made it: what is logged, what a replay must reproduce."""

    policy: str
    action: Action
    mode: Mode | None = None
    version: int | None = None
    content: dict[str, int] | None = None  # the packs the round draws from, as its attempt will record them
    choices: int | None = None
    seed: int | None = None
    level: int | None = None  # the round's step of difficulty (utility@4 on)
    probe: str | None = None  # the misconception the round checks (utility@5 on)
    skill: str | None = None
    rationale: list[Why]
    probability: float  # of this pick: 1 for a break or an end, which are rules, not draws
    candidates: list[Candidate] = Field(default_factory=list[Candidate])
    offers: list[Offer] | None = None  # a choice's two rounds, the drawn one first
    rate: bool = False  # ask how its round was once it is over

    def offered(self, i: int | None) -> Offer | None:
        return self.offers[i] if self.offers is not None and i is not None and 0 <= i < len(self.offers) else None


class Logged(Choice):
    """A decision as stored and exported: the choice, where it was made and when, and for a choice what was picked."""

    id: str
    session_id: str
    seq: int
    at: datetime
    picked: int | None = None
    picked_at: datetime | None = None

    def played(self) -> Mode | None:
        """The kind of round this decision put in front of the learner: a round's, a picked offer's, else None."""
        if self.action is Action.ROUND:
            return self.mode
        o = self.offered(self.picked)
        return o.mode if self.action is Action.CHOICE and o is not None else None


@dataclass(frozen=True)
class Past:
    """The session so far, oldest first: its start, each decision's action and the kind it put in play (a choice's
    picked offer; None for a choice not picked, a break or an end), each attempt's first answer and kind. Attempts,
    not decisions, say what was missed: a round can be left unanswered."""

    started: datetime
    decisions: Sequence[tuple[Action, Mode | None]] = ()
    answers: Sequence[tuple[Mode, bool]] = ()

    def rounds(self) -> list[Mode]:
        return [m for a, m in self.decisions if a in (Action.ROUND, Action.CHOICE) and m is not None]

    def since_break(self) -> int:
        n = 0
        for a, m in reversed(self.decisions):
            if a is Action.BREAK:
                break
            n += a is Action.ROUND or (a is Action.CHOICE and m is not None)
        return n

    def since_choice(self) -> int:
        """Rounds since the last choice was offered, or since the start."""
        n = 0
        for a, m in reversed(self.decisions):
            if a is Action.CHOICE:
                break
            n += a is Action.ROUND and m is not None
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
    liked: float = 0.3  # inside enjoyment's scale: a kind liked as much as can be is worth a change of mechanic
    misconception: float = 0.6  # as much as a diagnostic contrast: both are there to tell a cause from a slip
    # a nudge, not a priority: on simulated learners (who know a skill in every form alike) 0.8 cost 0.3 skills learnt
    # of 12.8 and 1.5 cost 0.6, as checks displace practice; 0.3 cost 0.15 and still checks every known skill in time
    transfer: float = 0.3


@dataclass(frozen=True)
class Policy:
    name: str = "utility"
    # 2 (0.8.0): choices, ratings and overrides. With none of them (a session snapshotted before, with no choice or
    # rating cadence, and a log with no ratings, picks or overrides) it decides exactly as 1 did, so `REPLAYS` keeps 1.
    # 3 (0.9.0): the Sounds round. Otherwise 2: each version weighs the kinds it had (`OFFERS`), so 1 and 2 are kept.
    # 4 (0.11.0): steps of difficulty. 3 and before lay out the grown-up's number of choices at no step, so they replay.
    # 5 (0.12.0): checking misconceptions. 4 and before give no probe bonus and draw no probe seed, so they replay.
    # 6 (0.13.0): transfer kinds and probes. 5 and before weigh only the practice kinds (`OFFERS`), so they replay.
    version: int = 6
    weights: Weights = field(default_factory=Weights)
    tau: float = 0.15  # softmax temperature: lower picks the best more often
    epsilon: float = 0.1  # share of every pick that is uniform over the eligible candidates

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def shapes(self) -> tuple[RoundShape, ...]:
        """The kinds of round this version weighs, in template order."""
        return tuple(s for s in SHAPES if s.mode in OFFERS[self.id])


# The kinds each version weighs. A new kind changes every decision's candidates and chances, so it comes with a new
# version, and a logged decision is remade against the kinds its own version had.
_ALL = frozenset(s.mode for s in SHAPES)
_PRACTICE = _ALL - set(rounds.HELD_OUT)
_BEFORE_SOUNDS = _PRACTICE - {Mode.SOUNDS}
OFFERS: dict[str, frozenset[Mode]] = {
    "utility@1": _BEFORE_SOUNDS,
    "utility@2": _BEFORE_SOUNDS,
    "utility@3": _PRACTICE,
    "utility@4": _PRACTICE,
    "utility@5": _PRACTICE,
    "utility@6": _ALL,
}
STEPS_FROM = 4  # the first version that chooses a step of difficulty
PROBES_FROM = 5  # the first version that checks misconceptions
TRANSFER_FROM = 6  # the first version that checks transfer

POLICY = Policy()
REPLAYS = frozenset(OFFERS)  # logged policies the current code remakes exactly


def kept(policy_id: str) -> Policy:
    """The policy a logged decision was made by, remade by the current code (`policy_id` is one of `REPLAYS`)."""
    return Policy(version=int(policy_id.rsplit("@", 1)[1]))


def entropy(p: float) -> float:
    """Binary entropy in bits: 1 at an even chance, 0 when the answer is certain."""
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def decide(
    k: Knowledge,
    past: Past,
    config: Config,
    key: str,
    now: datetime,
    policy: Policy = POLICY,
    likes: Mapping[str, float] | None = None,
) -> Choice:
    """The next decision for a session. `key` seeds the draw (the session id and the decision's number), so the same
    knowledge, session, config, key, time and `likes` (each kind's preference) always give the same decision."""
    played = past.rounds()
    if len(played) >= config.max_rounds:
        return Choice(policy=policy.id, action=Action.END, rationale=[Why.CAP_ROUNDS], probability=1.0)
    if (now - past.started).total_seconds() >= config.max_minutes * 60:
        return Choice(policy=policy.id, action=Action.END, rationale=[Why.CAP_MINUTES], probability=1.0)
    misses = past.misses()
    just_broke = bool(past.decisions) and past.decisions[-1][0] is Action.BREAK
    if not just_broke and misses >= FRUSTRATED and past.since_break() >= FRUSTRATED:
        return Choice(policy=policy.id, action=Action.BREAK, rationale=[Why.FRUSTRATION], probability=1.0)
    if not just_broke and config.break_every and past.since_break() >= config.break_every:
        return Choice(policy=policy.id, action=Action.BREAK, rationale=[Why.BREAK_DUE], probability=1.0)

    failed = past.answers[-1][0] if past.answers and not past.answers[-1][1] else None
    liked = likes or {}
    cands = [
        _candidate(k, s, past, config, now, policy, misses, failed, liked.get(s.mode.value, 0.0)) for s in policy.shapes
    ]
    open_ = [c for c in cands if c.set_aside is None]
    if not open_:  # never stuck: drop the softer filters first, the prerequisite gap last, a held-out kind never
        playable = [c for c in cands if c.set_aside is not SetAside.HELD_OUT]
        open_ = [c for c in playable if c.set_aside is not SetAside.PREREQUISITE] or playable
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
    top = max(c.utility for c in pool)
    rate = bool(config.rate_every) and (len(played) + 1) % config.rate_every == 0
    second = _second(pick, pool) if config.choice_every and past.since_choice() >= config.choice_every - 1 else None
    if second is not None:
        # The second is put forward as the best of the rest, not by chance, so it never says "exploration".
        offers = [
            _offer(pick, config, seed, misses, top, key),
            _offer(second, config, rng.randrange(SEED_LIMIT), misses, second.utility, key),
        ]
        return Choice(
            policy=policy.id,
            action=Action.CHOICE,
            rationale=[Why.OFFER],
            probability=pick.probability,
            candidates=logged,
            offers=offers,
            rate=rate,
        )
    o = _offer(pick, config, seed, misses, top, key)
    return Choice(
        policy=policy.id,
        action=Action.ROUND,
        mode=o.mode,
        version=o.version,
        content=o.content,
        choices=o.choices,
        seed=o.seed,
        level=o.level,
        probe=o.probe,
        skill=o.skill,
        rationale=o.rationale,
        probability=pick.probability,
        candidates=logged,
        rate=rate,
    )


def _why(c: Candidate, misses: int, top: float, probed: bool = False) -> list[Why]:
    why = [c.action]
    if probed:
        why.append(Why.PROBE)
    if c.contrast:
        why.append(Why.CONTRAST)
    if misses >= GUARDED:
        why.append(Why.EASIER)
    if c.liked > 0:
        why.append(Why.LIKED)
    if c.stepped > 0:
        why.append(Why.STEP_UP)
    elif c.stepped < 0 and misses < GUARDED:  # after misses, EASIER already says why
        why.append(Why.STEP_DOWN)
    if c.utility < top:
        why.append(Why.EXPLORE)
    return why


def _offer(c: Candidate, config: Config, seed: int, misses: int, top: float, key: str) -> Offer:
    shape = next(s for s in SHAPES if s.mode is c.mode)
    found = _probe_seed(c.mode, c.level, c.probe, key) if c.probe is not None and c.level is not None else None
    return Offer(
        mode=c.mode,
        version=shape.version,
        content=rounds.content_of(c.mode),
        choices=config.choices if c.level is None else rounds.TEMPLATES[c.mode].levels[c.level].choices,
        seed=seed if found is None else found,
        level=c.level,
        probe=None if found is None else c.probe,
        skill=c.skill,
        rationale=_why(c, misses, top, found is not None),
    )


def _probe_seed(mode: Mode, level: int, probe: str, key: str) -> int | None:
    """The first of `PROBE_TRIES` seeds, drawn from a generator of its own, whose round offers `probe`'s trap."""
    rng = random.Random(f"{key}:probe:{mode.value}")
    for _ in range(PROBE_TRIES):
        seed = rng.randrange(SEED_LIMIT)
        if probe in mistakes.traps(rounds.at_level(mode, level, seed)):
            return seed
    return None


def _second(first: Candidate, pool: Sequence[Candidate]) -> Candidate | None:
    """The best other candidate to offer beside `first`: of another mechanic if any is open, else another kind."""
    mech = {s.mode: s.mechanic for s in SHAPES}
    others = [c for c in pool if c.mode is not first.mode]
    unlike = [c for c in others if mech[c.mode] is not mech[first.mode]]
    best = unlike or others
    return max(best, key=lambda c: (c.utility, c.mode.value)) if best else None


def _candidate(
    k: Knowledge,
    shape: RoundShape,
    past: Past,
    config: Config,
    now: datetime,
    policy: Policy,
    misses: int,
    failed: Mode | None,
    liked: float = 0.0,
) -> Candidate:
    w = policy.weights
    g = k.graph
    me = k.state(shape.primary)
    placing = k.counted < PLACING
    held = shape.mode in rounds.HELD_OUT and policy.version >= TRANSFER_FROM
    due = (
        held
        and me.p >= MASTERED
        and k.practised.get(shape.primary, 0) >= CHECK_AFTER
        and not k.transferred(shape.primary)
    )
    if due:
        action = Why.TRANSFER
    elif not me.seen:
        action = Why.PLACEMENT if placing else Why.INTRODUCE
    elif me.p < MASTERED:
        action = Why.PRACTISE
    elif me.own and me.recall(now) < DUE:  # a skill a grown-up said they can do, with no answer yet, is consolidated
        action = Why.REVIEW
    else:
        action = Why.CONSOLIDATE

    level, stepped = _step(k, shape, misses) if policy.version >= STEPS_FROM else (None, 0)
    laid = config.choices if level is None else rounds.TEMPLATES[shape.mode].levels[level].choices
    p_right = k.p_right(shape.skills, shape.options(laid))
    before = g.before.get(shape.primary, frozenset())
    ready = min((k.p(q) for q in before), default=1.0)
    learning = (1 - me.p) * ready
    reach = sum(1 for s in before | g.after.get(shape.primary, frozenset()) if not k.state(s).seen)
    information = entropy(p_right) * (1 + w.reach * reach) * (w.placing if placing else 1.0)
    retention = 1 - me.recall(now) if me.own and me.p >= MASTERED else 0.0
    played = past.rounds()
    switch = 1.0 if played and next(s for s in SHAPES if s.mode is played[-1]).mechanic is not shape.mechanic else 0.0
    enjoyment = 0.7 * max(0.0, 1 - abs(p_right - 0.75) / 0.75) + 0.3 * switch + w.liked * liked
    frustration = (1 - p_right) * (1 + misses)
    recent = played[-4:]
    repetition = sum(m is shape.mode for m in recent) / 4

    contrast, diagnostic = False, 0.0
    if failed is not None and failed is not shape.mode:
        lost = next(s for s in SHAPES if s.mode is failed)
        shared = set(shape.skills) & set(lost.skills)
        if shared and set(lost.skills) - set(shape.skills):
            contrast = True
            diagnostic = sum(entropy(k.p(s)) for s in shared) / len(shared)

    probe, misconception = _probe(k, shape.mode, level) if policy.version >= PROBES_FROM else (None, 0.0)

    set_aside: SetAside | None = None
    if held and not due:
        set_aside = SetAside.HELD_OUT
    elif any((k.state(q).own >= 2 or k.state(q).told) and k.p(q) < 0.3 for q in before):
        set_aside = SetAside.PREREQUISITE
    elif misses >= GUARDED and p_right < 0.6:
        set_aside = SetAside.FRUSTRATION
    elif played[-2:] == [shape.mode, shape.mode]:
        set_aside = SetAside.REPEAT

    utility = (
        w.learning * learning
        + w.information * information
        + w.retention * retention
        + w.enjoyment * enjoyment
        - w.frustration * frustration
        - w.repetition * repetition
        + w.diagnostic * diagnostic
        + w.misconception * misconception
        + w.transfer * due
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
        liked=round(liked, 6),
        level=level,
        stepped=stepped,
        probe=probe,
        misconception=misconception,
        utility=round(utility, 6),
        probability=0.0,
        set_aside=set_aside,
    )


def _probe(k: Knowledge, mode: Mode, level: int | None) -> tuple[str | None, float]:
    """The misconception a round of `mode` at `level` would check, and its bonus: the suspected first, then by id."""
    if level is None:
        return None, 0.0
    able = [
        (m, t)
        for m, t in k.mistakes.items()
        if t.open and mode in mistakes.PROBES.get(m, {}) and level >= mistakes.PROBES[m][mode]
    ]
    if not able:
        return None, 0.0
    m, t = min(able, key=lambda x: (x[1].status is not Status.SUSPECTED, x[0]))
    return m, 1.0 if t.status is Status.SUSPECTED else 0.5


def _step(k: Knowledge, shape: RoundShape, misses: int) -> tuple[int, int]:
    """The step a round of `shape` is played at, and whether that is harder (1) or easier (-1) than the last one."""
    steps = len(rounds.TEMPLATES[shape.mode].levels)
    stair = k.stairs.get(shape.mode)
    # no stair yet: the easiest step, or halfway up for a skill already known
    start = steps // 2 if k.p(shape.primary) >= MASTERED else 0
    level = stair.level if stair is not None else start
    if misses >= GUARDED:
        level = max(0, level - 1)
    if stair is None:
        return level, 0
    return level, (level > stair.last) - (level < stair.last)


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
    Why.OFFER: "Two to pick from, so they choose what comes next.",
    Why.LIKED: "They have liked this kind of round.",
    Why.STEP_UP: "A step harder than last time: {step}.",
    Why.STEP_DOWN: "A step easier than last time: {step}.",
    Why.PROBE: "It offers a likely mix-up ({probe}), to tell a mix-up from a slip.",
    Why.TRANSFER: "Known in its own kind of round, so checked in a new one, to see that it carries over: {skill}.",
}


def step_says(mode: Mode | None, level: int | None) -> str:
    """A step of difficulty in a grown-up's words ("numbers to 10, 4 to pick from"); empty for no step."""
    if mode is None or level is None:
        return ""
    levels = rounds.TEMPLATES[mode].levels
    return levels[level].says if 0 <= level < len(levels) else ""


def explain(c: Choice, titles: Mapping[str, str], config: Config, rounds_played: int, picked: int | None = None) -> str:
    """The rationale in words, for the grown-up (the codes stay in the log). A choice picked is explained by the
    offer picked, after the choice itself."""
    o = c.offered(picked)
    step = step_says(o.mode, o.level) if o is not None else step_says(c.mode, c.level)
    skill_id = o.skill if o is not None else c.skill or ""
    skill = titles.get(skill_id, skill_id)
    played = f"{rounds_played} round" + ("" if rounds_played == 1 else "s")
    codes = [*c.rationale, *(o.rationale if o is not None else [])]
    probe_id = (o.probe if o is not None else c.probe) or ""
    known = content.load().misconceptions.get(probe_id)
    probe = known.title.lower() if known is not None else probe_id
    return " ".join(
        _SAY[w].format(skill=skill, rounds=played, minutes=config.max_minutes, step=step, probe=probe) for w in codes
    )
