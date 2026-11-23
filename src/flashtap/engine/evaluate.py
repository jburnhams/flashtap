"""How well a learner model predicts the next first answer (spec §16, "Assessment: held-out predictive log loss, Brier,
calibration"): each attempt is predicted from the attempts before it only, then scored.

Three predictors:

- `rule`: the share right among the last `window` counted answers for the round's primary skill, with one right and
  one wrong added so a first answer is never predicted as certain; the share right over all training answers when the
  skill has none yet. The baseline the plan's exit criterion names: what a grown-up would say from memory.
- `bkt`: the P2 estimator (each skill on its own, the round's primary skill only, guess 1 in the tiles).
- `engine`: the adaptive engine's model (`model.Knowledge`: BKT with the skill graph placing unseen skills, and a round
  predicted from every skill it needs).

`fit` chooses each predictor's numbers on training learners by grid search, so the comparison on held-out learners is
between fitted models (§10: "calibrate from data, not arbitrary universal values").
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import product

from pydantic import BaseModel

from flashtap.engine.model import Graph, Knowledge, Params
from flashtap.learners.evidence import Event, judge, ordered

EPS = 1e-6
PRIORS = (0.1, 0.25, 0.4)
LEARNS = (0.02, 0.05, 0.15, 0.3)
SLIPS = (0.05, 0.12, 0.2)
WINDOWS = (3, 5, 10, 20)

Log = Sequence[Event]


class Score(BaseModel):
    model: str
    description: str
    attempts: int
    log_loss: float
    brier: float


def score(model: str, description: str, pairs: Iterable[tuple[float, bool]]) -> Score:
    ps = list(pairs)
    n = len(ps)
    if not n:
        return Score(model=model, description=description, attempts=0, log_loss=0.0, brier=0.0)
    ll = -sum(math.log(min(max(p, EPS), 1 - EPS)) if y else math.log(1 - min(max(p, EPS), 1 - EPS)) for p, y in ps) / n
    brier = sum((p - y) ** 2 for p, y in ps) / n
    return Score(model=model, description=description, attempts=n, log_loss=round(ll, 6), brier=round(brier, 6))


def _primary(e: Event) -> str:
    return next(s.skill for s in e.skills if s.role == "primary")


def engine_pairs(log: Log, g: Graph, params: Params) -> list[tuple[float, bool]]:
    k = Knowledge(g, params)
    out: list[tuple[float, bool]] = []
    for e in ordered(log):
        if e.struck is None:
            out.append((k.p_right([s.skill for s in e.skills], e.options), e.first_correct))
        k.observe(e)
    return out


def bkt_pairs(log: Log, params: Params) -> list[tuple[float, bool]]:
    """Each skill alone: the engine's model with no graph, predicting from the primary skill only."""
    k = Knowledge(Graph((), {}, {}), params)
    out: list[tuple[float, bool]] = []
    for e in ordered(log):
        if e.struck is None:
            out.append((k.p_right([_primary(e)], e.options), e.first_correct))
        k.observe(e)
    return out


def rule_pairs(log: Log, window: int, base: float) -> list[tuple[float, bool]]:
    seen: dict[str, list[bool]] = {}
    shown: set[str] = set()
    out: list[tuple[float, bool]] = []
    for e in ordered(log):
        if e.struck is None:
            recent = seen.get(_primary(e), [])[-window:]
            out.append(((sum(recent) + 1) / (len(recent) + 2) if recent else base, e.first_correct))
        for u in judge(e, shown):
            if u.counted:
                seen.setdefault(u.skill, []).append(e.first_correct)
    return out


@dataclass(frozen=True)
class Fitted:
    engine: Params
    bkt: Params
    window: int
    base: float


DEFAULT = Fitted(engine=Params(), bkt=Params(), window=5, base=0.5)


def _mean_ll(pairs: list[tuple[float, bool]]) -> float:
    return score("", "", pairs).log_loss


def fit(logs: Sequence[Log], g: Graph) -> Fitted:
    """The numbers that predict the training learners best, each predictor on its own grid."""
    grid = [Params(prior=p, learn=lr, slip=s) for p, lr, s in product(PRIORS, LEARNS, SLIPS)]
    engine = min(grid, key=lambda ps: _mean_ll([x for log in logs for x in engine_pairs(log, g, ps)]))
    bkt = min(grid, key=lambda ps: _mean_ll([x for log in logs for x in bkt_pairs(log, ps)]))
    answers = [e.first_correct for log in logs for e in log if e.struck is None]
    base = sum(answers) / len(answers) if answers else 0.5
    window = min(WINDOWS, key=lambda w: _mean_ll([x for log in logs for x in rule_pairs(log, w, base)]))
    return Fitted(engine=engine, bkt=bkt, window=window, base=round(base, 6))


def scores(logs: Sequence[Log], g: Graph, f: Fitted = DEFAULT) -> list[Score]:
    """Every predictor on `logs`, best (lowest log loss) first."""
    out = [
        score(
            "engine",
            f"Adaptive engine's model: graph-placed BKT, {f.engine.label()}",
            (x for log in logs for x in engine_pairs(log, g, f.engine)),
        ),
        score("bkt", f"BKT, each skill alone: {f.bkt.label()}", (x for log in logs for x in bkt_pairs(log, f.bkt))),
        score(
            "rule",
            f"Share right of the last {f.window} for the skill (base {f.base:g})",
            (x for log in logs for x in rule_pairs(log, f.window, f.base)),
        ),
    ]
    return sorted(out, key=lambda s: (s.log_loss, s.model))
