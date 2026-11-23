"""Estimators of mastery, behind one interface (spec §10: "multiple interchangeable estimators: rule baseline, BKT, ...").

An estimator folds one skill's counted observations, oldest first, into an `Estimate`: the probability the skill is
known (or the recent share right, for the rule) and how many observations it used. It is a pure function of that
list, so replaying the same event log gives the same numbers (the PR's exit criterion; tests/unit/test_learners.py).
Which observations count, and in what order, is decided once in `evidence.py`, not by each estimator.

Every number below is an experimental default, as the spec says of its own (§0, "requiring empirical calibration"):
they are here so the screens and the replay can be built and tested, and will be fitted from real attempts (P3's held
out log loss) rather than tuned by hand.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from flashtap.learners.evidence import Observation


class Estimate(BaseModel):
    model: str  # "bkt@1": the estimator and its version, so a stored or exported number says what made it
    p: float  # the chance the skill is known (BKT) or the recent share right (rule)
    used: int  # observations folded in
    told: int = 0  # grown-ups' overrides folded in (BKT only; the rule is the share of answers, so it takes none)


class Estimator(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> int: ...
    @property
    def description(self) -> str: ...

    def estimate(self, observations: Sequence[Observation], told: Sequence[tuple[datetime, float]] = ()) -> Estimate:
        """`told`: overrides standing, as (when, the chance it sets), oldest first."""
        ...


def model_id(e: Estimator) -> str:
    return f"{e.name}@{e.version}"


@dataclass(frozen=True)
class RuleBaseline:
    """The share right among the last `window` counted first answers: what a grown-up would say from memory, and the
    baseline P3's scheduler has to beat."""

    window: int = 5
    name: str = "rule"
    version: int = 1
    description: str = "Share right among the last 5 counted first answers"

    def estimate(self, observations: Sequence[Observation], told: Sequence[tuple[datetime, float]] = ()) -> Estimate:
        recent = observations[-self.window :]
        right = sum(o.correct for o in recent)
        return Estimate(model=model_id(self), p=right / len(recent) if recent else 0.0, used=len(recent))


PLACE_GUESS = 0.05  # an arrangement is rarely right by luck: far fewer than 1 in k ways are right


@dataclass(frozen=True)
class BKT:
    """Bayesian knowledge tracing (Corbett and Anderson, 1995), one skill at a time.

    P(right) = P(known)(1 - slip) + (1 - P(known)) guess. After an answer, P(known) is updated by Bayes' rule, then the
    chance of learning between rounds is added: P(known) += (1 - P(known)) learn.

    The guess is per round, not per skill: 1 in k for a one-tap round of k tiles, `PLACE_GUESS` for an arrangement.
    The spec warns that 1/k is not exact (distractors differ in pull, §10); it is the default until there is data.
    """

    prior: float = 0.2  # P(known) before any evidence; unobserved skills are reported as such, never as this number
    learn: float = 0.1
    slip: float = 0.1
    name: str = "bkt"
    version: int = 1
    description: str = "Bayesian knowledge tracing: prior 0.2, learn 0.1, slip 0.1, guess 1 in the number of tiles"

    def estimate(self, observations: Sequence[Observation], told: Sequence[tuple[datetime, float]] = ()) -> Estimate:
        known = self.prior
        pending = list(told)
        for o in observations:
            while pending and pending[0][0] <= o.at:  # an override sets the estimate; later answers move it on
                known = pending.pop(0)[1]
            guess = 1 / o.options if o.options else PLACE_GUESS
            if o.correct:
                seen = known * (1 - self.slip) / (known * (1 - self.slip) + (1 - known) * guess)
            else:
                seen = known * self.slip / (known * self.slip + (1 - known) * (1 - guess))
            known = seen + (1 - seen) * self.learn
        if pending:
            known = pending[-1][1]
        return Estimate(model=model_id(self), p=known, used=len(observations), told=len(told))


RULE = RuleBaseline()
BAYES = BKT()
ESTIMATORS: tuple[Estimator, ...] = (BAYES, RULE)
