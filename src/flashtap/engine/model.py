"""The adaptive engine's learner model: what the evidence says each skill's chance of being known is, the skill graph
filling in what has not been seen, and how likely a learner is to get a given round right.

It is the P2 estimators' BKT (src/flashtap/learners/estimators.py) with three changes the scheduler needs (spec §10,
§12, §13):

- **The skill graph places a learner.** A right answer to a round written to assess a skill (primary) raises every
  strong prerequisite that has no evidence of its own towards that skill's estimate: knowing how many are in a group
  by the last number counted implies counting objects. A wrong primary answer lowers every dependent with no evidence
  of its own to at most that skill's estimate. So a few probes place a learner anywhere in the graph, from evidence and
  never from an age, and a skill's own evidence always takes over from what was inferred.
- **A round needs all its skills.** P(right) = P(all known)(1 - slip) + (1 - P(all known)) guess, with P(all known) the
  product of the estimates of every skill the round names (primary, secondary and confound alike): a Counting round
  is lost by a learner who counts but cannot read the numeral. This is the prediction the held-out log loss scores.
- **Retention.** Each skill keeps a half-life, one day after its first right answer, doubled by a right answer at
  least a day after the last, halved by a wrong one; the chance it is still recalled is 2^(-days since / half-life).
  The scheduler uses it to bring a skill back for review (§13 "spaced reviews"); the prediction does not, until real
  delayed answers say how much forgetting there is (§13 "calibrate retention schedules on real delayed recall data").

**Steps of difficulty** (spec §6; `rounds.Level`). Each kind of round keeps a staircase (`Stair`): the step the
learner's last round of that kind was played at, moved up after `UP` first answers right in a row at it and down after
`DOWN` missed in a row. A right answer at a harder step than the stair's (or a miss at an easier one) moves the stair
there at once. Up after three and down after two settles where most first answers go right (near the three in four the
scheduler aims for), and a run of misses brings the work down faster than a run of successes takes it up: the spec's
"constrain frustration" (§12). Only rounds the engine made at a step move a stair; rounds played by hand carry none.
The step changes the chance of a lucky answer (more tiles, less luck), not the skill's estimate: BKT stays one
estimate per skill, over every step it was seen at (the spec's "core capability + parameters", §4).

A grown-up's override (`evidence.Told`) sets a skill's estimate when it was made and marks it as having evidence of
its own, so the graph no longer fills it in; "can do it" lifts its unseen prerequisites as a right answer would, and
"not yet" caps its unseen dependents as a miss would (§13: "rapid acceleration, regression and manual overrides").

**Misconceptions** (`learners/misconceptions.py`): each attempt's traps are folded into one tally per misconception
(`mistakes`), the same fold the Learner screen uses, so the scheduler can check a suspected one with a round that
offers its trap. They move no estimate: the answers were already counted as wrong. Nor does speed: how quickly a
learner answers is reported (`learners/fluency.py`) and never read here (§10).

Which answers count, and for which skill, is `evidence.judge`, shared with the Learner screen, so the engine and the
grown-up's report never count differently. The fold is incremental and ordered (`evidence.ordered`), so the same log
always gives the same knowledge, which a replay of the engine's decisions relies on (`replay.py`).
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from flashtap import content, rounds
from flashtap.content import Registry
from flashtap.content.model import Relation
from flashtap.learners.estimators import PLACE_GUESS
from flashtap.learners.evidence import TOLD_P, Event, Told, judge, ordered
from flashtap.learners.misconceptions import Tally
from flashtap.learners.misconceptions import observe as tally
from flashtap.mechanics import PLACE, Mechanic, Mode

DAY = 86400.0
UP = 3  # first answers right in a row at a step before the next step up
DOWN = 2  # missed in a row at a step before the step below


@dataclass(frozen=True)
class Params:
    """BKT's numbers. The defaults are the P2 estimator's; `simulate.fit` chooses them from training learners."""

    prior: float = 0.2
    learn: float = 0.1
    slip: float = 0.1
    imply: float = 0.9  # a right primary answer lifts its unseen prerequisites to this share of its own estimate

    def label(self) -> str:
        return f"prior {self.prior:g}, learn {self.learn:g}, slip {self.slip:g}"


@dataclass(frozen=True)
class Graph:
    """The strong prerequisites between the skills the rounds assess, closed over the whole content graph: a chain
    through a skill no round assesses yet still links its two ends. `before[s]` are the skills s needs; `after[s]`
    the skills that need s."""

    skills: tuple[str, ...]
    before: Mapping[str, frozenset[str]]
    after: Mapping[str, frozenset[str]]

    def depth(self, skill: str) -> int:
        """The longest chain of prerequisites under `skill`: 0 for a skill that needs none."""
        return max((self.depth(q) + 1 for q in self.before.get(skill, frozenset())), default=0)


def graph(registry: Registry | None = None, skills: Iterable[str] | None = None) -> Graph:
    r = registry or content.load()
    wanted = tuple(
        sorted(set(skills) if skills is not None else {s for t in rounds.TEMPLATES.values() for s, _ in t.skills})
    )
    direct: dict[str, set[str]] = {}
    for e in r.edges:
        if e.relation is Relation.PREREQUISITE_STRONG:
            direct.setdefault(e.target, set()).add(e.source)

    def closure(s: str) -> set[str]:
        seen: set[str] = set()
        frontier = direct.get(s, set())
        while frontier:  # the packs refuse prerequisite cycles (content check), so this ends
            seen |= frontier
            frontier = {p for q in frontier for p in direct.get(q, set())} - seen
        return seen

    before = {s: frozenset(closure(s) & set(wanted)) for s in wanted}
    after = {s: frozenset(d for d in wanted if s in before[d]) for s in wanted}
    return Graph(wanted, before, after)


@dataclass
class SkillState:
    p: float
    own: int = 0  # counted answers of its own; 0 means the estimate is the prior or inferred from the graph
    right: int = 0
    last_seen: datetime | None = None  # the latest counted answer
    last_right: datetime | None = None
    half_life: float = 0.0  # days; 0 until the first right answer
    told: bool = False  # a grown-up's override set it: evidence of its own, so the graph leaves it alone

    @property
    def seen(self) -> bool:
        """Whether anything but the graph speaks for it: an answer of its own, or a grown-up."""
        return self.own > 0 or self.told

    def recall(self, now: datetime) -> float:
        """The chance it is still remembered `now`: 1 just after a right answer, halving every half-life."""
        if self.last_right is None or self.half_life <= 0:
            return 0.0
        days = max(0.0, (now - self.last_right).total_seconds() / DAY)
        return 2 ** (-days / self.half_life)


@dataclass
class Stair:
    """One kind of round's step of difficulty for a learner: where the next round of it is played, and the run at it."""

    level: int  # the step the next round of this kind is played at (before any easing after misses)
    last: int  # the step its last round was played at
    right: int = 0  # first answers right in a row at `level`
    wrong: int = 0  # missed in a row at `level`

    def climb(self, level: int, right: bool, steps: int) -> None:
        self.last = level
        if level != self.level:
            # A round at another step (eased after misses, or a pick from a choice) speaks for the stair only when it
            # says more than the stair knows: right at a harder step, or missed at an easier one.
            if right != (level > self.level):
                return
            self.level, self.right, self.wrong = level, 0, 0
        if right:
            self.right, self.wrong = self.right + 1, 0
        else:
            self.right, self.wrong = 0, self.wrong + 1
        if self.right >= UP and self.level < steps - 1:
            self.level, self.right = self.level + 1, 0
        elif self.wrong >= DOWN and self.level > 0:
            self.level, self.wrong = self.level - 1, 0


def guess(options: int) -> float:
    """The chance of a lucky first answer: 1 in the tiles for a one-tap round, `PLACE_GUESS` for an arrangement."""
    return 1 / options if options else PLACE_GUESS


@dataclass
class Knowledge:
    """Every skill's state after folding a log, oldest first. `observe` takes one more attempt; `p_right` predicts one."""

    graph: Graph
    params: Params = field(default_factory=Params)
    skills: dict[str, SkillState] = field(default_factory=dict[str, SkillState])
    shown: set[str] = field(default_factory=set[str])
    counted: int = 0  # counted answers over every skill
    stairs: dict[Mode, Stair] = field(default_factory=dict[Mode, Stair])  # per kind, once played at a step
    mistakes: dict[str, Tally] = field(default_factory=dict[str, Tally])  # per misconception a round has offered

    def state(self, skill: str) -> SkillState:
        s = self.skills.get(skill)
        if s is None:
            s = self.skills[skill] = SkillState(p=self.params.prior)
        return s

    def p(self, skill: str) -> float:
        return self.state(skill).p

    def p_right(self, skills: Sequence[str], options: int) -> float:
        """The chance of a right first answer to a round needing `skills`, offering `options` tiles (0: arranged)."""
        known = math.prod(self.p(s) for s in skills)
        return known * (1 - self.params.slip) + (1 - known) * guess(options)

    def observe(self, e: Event) -> None:
        tally(self.mistakes, e)
        if e.level is not None and e.struck is None:
            mode = Mode(e.mode)
            steps = len(rounds.TEMPLATES[mode].levels)
            self.stairs.setdefault(mode, Stair(level=e.level, last=e.level)).climb(e.level, e.first_correct, steps)
        for u in judge(e, self.shown):
            if not u.counted:
                continue
            self.counted += 1
            s = self.state(u.skill)
            s.p = self._update(s.p, e.first_correct, e.options)
            s.own += 1
            s.last_seen = e.presented_at
            if e.first_correct:
                s.right += 1
                if s.last_right is None:
                    s.half_life = 1.0
                elif (e.presented_at - s.last_right).total_seconds() >= DAY:
                    s.half_life *= 2
                s.last_right = e.presented_at
            elif s.half_life > 0:
                s.half_life = max(1.0, s.half_life / 2)
            if u.role == "primary":
                self._spread(u.skill, e.first_correct)

    def tell(self, t: Told) -> None:
        s = self.state(t.skill)
        s.p = TOLD_P[t.says]
        s.told = True
        self._spread(t.skill, t.says == "can")

    def _update(self, known: float, right: bool, options: int) -> float:
        slip, g, learn = self.params.slip, guess(options), self.params.learn
        if right:
            seen = known * (1 - slip) / (known * (1 - slip) + (1 - known) * g)
        else:
            seen = known * slip / (known * slip + (1 - known) * (1 - g))
        return seen + (1 - seen) * learn

    def _spread(self, skill: str, right: bool) -> None:
        p = self.p(skill)
        if right:
            for q in self.graph.before.get(skill, frozenset()):
                if not self.state(q).seen:
                    self.state(q).p = max(self.p(q), self.params.imply * p)
        else:
            for d in self.graph.after.get(skill, frozenset()):
                if not self.state(d).seen:
                    self.state(d).p = min(self.p(d), p)


def fold(events: Iterable[Event], g: Graph, params: Params | None = None, told: Iterable[Told] = ()) -> Knowledge:
    """The log folded oldest first; each override in `told` (those standing, `evidence.told_as_of`) is taken at its
    time, before an answer shown at the same moment."""
    k = Knowledge(g, params or Params())
    pending = sorted(told, key=lambda t: (t.at, t.id))
    for e in ordered(events):
        while pending and pending[0].at <= e.presented_at:
            k.tell(pending.pop(0))
        k.observe(e)
    for t in pending:
        k.tell(t)
    return k


@dataclass(frozen=True)
class RoundShape:
    """What a round of one kind needs and offers, without building it: enough to predict and schedule."""

    mode: Mode
    version: int
    mechanic: Mechanic
    primary: str
    skills: tuple[str, ...]
    roles: tuple[tuple[str, str], ...]

    def options(self, choices: int) -> int:
        return 0 if self.mechanic in PLACE else choices


SHAPES: tuple[RoundShape, ...] = tuple(
    RoundShape(
        mode=t.mode,
        version=t.version,
        mechanic=t.mechanic,
        primary=next(s for s, r in t.skills if r.value == "primary"),
        skills=tuple(s for s, _ in t.skills),
        roles=tuple((s, r.value) for s, r in t.skills),
    )
    for t in rounds.TEMPLATES.values()
)
SHAPE = {s.mode: s for s in SHAPES}
