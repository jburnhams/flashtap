"""Fluency: how quickly a learner gives a right first answer on a skill (spec §10 "fluency distribution"), reported
beside the estimates and never folded into them: §10, "never treat response speed as mastery without controlling for
modality, motor ability, device and fatigue". A slow right answer is still right, so no state, estimate or engine
choice reads this; it is for a grown-up to see whether an answer has become automatic.

Which first answers it reads, and why each rule is there (the spec's four confounds):

- **Right, first, unstruck, counted, on a round written to assess the skill** (primary): a wrong answer's time says
  nothing about how fluent a right one is, and a skill only needed by the round (secondary or confound) did not set
  its pace.
- **Fatigue**: only rounds presented within `FRESH` of their session's first round. Later ones may be slow because the
  learner is tired, not because the skill is.
- **A pause**: a first answer slower than `AWAY` is left out. The learner was probably away or talking, not thinking.
- **Modality, motor ability and device**: a time is never compared with another kind of round, another step of
  difficulty (more tiles, more to look at) or another learner. `seconds` is the plain median for the grown-up, but
  `trend` compares the learner only with themself on the same kind and step: each time is divided by the median of
  that (kind, step), and the newer half of those ratios is set against the older half. A learner who taps slowly on
  every kind, or on a slow device, is therefore "steady", not "slow". Quick look includes the moment its pictures
  show, and a spoken prompt the time it takes to say: both are the same each time within a kind, so the trend is not
  moved by them.

Both times come from the device's clock (presented_at and answered_at), so a wrong clock moves both together.
"""

import statistics
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from flashtap.learners.evidence import Event, Use

FRESH = timedelta(minutes=10)  # rounds this early in a session; a session is 15 minutes at most by default
AWAY = 60.0  # seconds: a first answer slower than this was a pause, not thinking
RECENT = 8  # the latest answers the typical time and its spread are taken over
TREND = 6  # answers before a trend is named (three in each half)
QUICKER = 0.8  # the newer half's median ratio at or below this share of the older's is "quicker"
SLOWER = 1.25  # and at or above this, "slower"

Trend = Literal["quicker", "steady", "slower"]


class Fluency(BaseModel):
    seconds: float  # the median time to a right first answer, over the latest `used`
    low: float  # the quickest quarter's edge, and the slowest's: the spread of those times
    high: float
    used: int
    trend: Trend | None  # against their own earlier answers on the same kind and step; None until `TREND` answers


def starts(events: Iterable[Event]) -> dict[str, datetime]:
    """Each session's first round, from every attempt in it (struck or not: the learner was still playing)."""
    out: dict[str, datetime] = {}
    for e in events:
        out[e.session_id] = min(out.get(e.session_id, e.presented_at), e.presented_at)
    return out


def timed(uses: Iterable[Use], started: Mapping[str, datetime]) -> list[Event]:
    """The attempts whose time speaks for fluency, oldest first (the rules above)."""
    return [
        u.event
        for u in uses
        if u.counted
        and u.role == "primary"
        and u.event.first_correct
        and u.event.struck is None
        and u.event.presented_at - started.get(u.event.session_id, u.event.presented_at) <= FRESH
        and u.event.seconds <= AWAY
    ]


def _trend(es: list[Event]) -> Trend | None:
    if len(es) < TREND:
        return None
    groups: dict[tuple[str, int | None], list[float]] = {}
    for e in es:
        groups.setdefault((e.mode, e.level), []).append(e.seconds)
    typical = {k: statistics.median(v) for k, v in groups.items()}
    ratios = [e.seconds / typical[(e.mode, e.level)] if typical[(e.mode, e.level)] > 0 else 1.0 for e in es]
    half = len(ratios) // 2
    older, newer = statistics.median(ratios[:half]), statistics.median(ratios[-half:])
    if older <= 0:
        return "steady"
    change = newer / older
    return "quicker" if change <= QUICKER else "slower" if change >= SLOWER else "steady"


def fluency(uses: Iterable[Use], started: Mapping[str, datetime]) -> Fluency | None:
    """One skill's fluency from its uses (evidence.uses), or None with no right first answer that qualifies."""
    es = timed(uses, started)
    if not es:
        return None
    recent = [e.seconds for e in es[-RECENT:]]
    low, high = (min(recent), max(recent)) if len(recent) < 4 else statistics.quantiles(recent, n=4)[::2]
    return Fluency(
        seconds=round(statistics.median(recent), 1),
        low=round(low, 1),
        high=round(high, 1),
        used=len(recent),
        trend=_trend(es),
    )
