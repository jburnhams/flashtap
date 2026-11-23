"""Engagement, kept apart from what a learner knows (spec §11): how they said rounds were, what they picked when
offered a choice, and the patterns in how they answer, all as hypotheses for a grown-up, never labels about the child.

Three things live here, each computed from the log on every read, as the estimates are:

- **Ratings** (`Rated`): the three faces after a round, `1` liked it, `0` all right, `-1` did not. Optional and
  occasional (the `rate_every` setting); a round nobody rated has none. Only the enjoyment scale is asked today.
- **Preferences** (`preferences`): one number per kind of round, from -1 to 1, that the engine adds to a candidate's
  enjoyment (engine/policy.py). Each rating adds its value; each pick between two activities adds a half to the one
  picked and takes a half from the one passed over. The sum is divided by the number of signals plus `SHRINK`, so a
  single face moves it a little and it takes several to move it far (§11: "preference models must account for
  challenge, novelty, exposure and recency": challenge stays the engine's own term, this is only what they said and
  chose). It never touches the estimates of what they know.
- **Patterns** (`hypotheses`): the spec's table of behaviour patterns (§11), each with the hypotheses that compete to
  explain it and a low-risk thing to try, worded as "could be", over enough rounds that one bad day does not count.
  Speed is only ever read beside accuracy and tries, never alone (§10: "never treat response speed as mastery").

Every threshold is a first guess, like the estimators' (they are here so the screens can be built and tested).
"""

import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel

from flashtap.learners.evidence import Event, ordered

Scale = Literal["enjoyment"]
SHRINK = 3.0  # pseudo-signals at zero that every preference is averaged with
PICK = 0.5  # what a pick counts for beside a rating
MIN_ROUNDS = 5  # rounds of a kind before a pattern about it is named
QUICK_S = 3.0  # a median first answer quicker than this, with high accuracy, is "quick"
SLOW_S = 15.0  # and slower than this, with low accuracy, is "long hesitation"


class Rated(BaseModel):
    """One rating, as the log keeps it and an export carries it."""

    event_id: str
    session_id: str
    mode: str
    scale: Scale = "enjoyment"
    value: int  # -1, 0 or 1
    at: AwareDatetime  # when the server took it


class Pick(BaseModel):
    """A choice between two activities, answered: the kind picked, the one passed over, and when."""

    picked: str
    passed: str
    at: AwareDatetime


class Offered(BaseModel):
    """A choice between two activities as offered: the two kinds, and the one picked and when (None: not picked)."""

    first: str
    second: str
    picked: str | None = None
    at: AwareDatetime | None = None

    def pick(self) -> Pick | None:
        if self.picked is None or self.at is None:
            return None
        return Pick(picked=self.picked, passed=self.second if self.picked == self.first else self.first, at=self.at)


def as_of_ratings(ratings: Iterable[Rated], at: datetime) -> list[Rated]:
    return [r for r in ratings if r.at <= at]


def preferences(ratings: Iterable[Rated], picks: Iterable[Pick]) -> dict[str, float]:
    """Each kind's preference, -1 to 1; a kind with no signal is absent (0 to the engine)."""
    total: dict[str, float] = {}
    n: dict[str, int] = {}
    for r in ratings:
        total[r.mode] = total.get(r.mode, 0.0) + r.value
        n[r.mode] = n.get(r.mode, 0) + 1
    for p in picks:
        total[p.picked] = total.get(p.picked, 0.0) + PICK
        total[p.passed] = total.get(p.passed, 0.0) - PICK
        n[p.picked] = n.get(p.picked, 0) + 1
        n[p.passed] = n.get(p.passed, 0) + 1
    return {m: max(-1.0, min(1.0, total[m] / (n[m] + SHRINK))) for m in sorted(total)}


class KindRow(BaseModel):
    """One kind of round as this learner has played it: how it went, how it was rated, how often picked."""

    mode: str
    title: str
    rounds: int
    right_first: int  # first answers right
    median_seconds: float | None  # from showing the round to the first answer
    mean_tries: float | None
    left: int  # rounds moved on from before they were over
    liked: int
    okay: int
    disliked: int
    offered: int  # times it was one of two in a choice they answered (a choice left unpicked counts for neither)
    picked: int
    preference: float  # what the engine adds for it: -1 to 1, 0 with no signal


class Hypothesis(BaseModel):
    """A pattern seen, what could explain it, and what to try: never a label about the child."""

    code: Literal["quick_and_right", "stuck", "late_decline", "disliked", "passed_over"]
    mode: str | None  # the kind it is about; None for one about whole sessions
    seen: str
    could_be: str
    try_: str


class Engagement(BaseModel):
    kinds: list[KindRow]
    hypotheses: list[Hypothesis]


def _secs(e: Event) -> float:
    return (e.answered_at - e.presented_at).total_seconds()


def report(
    events: Iterable[Event], ratings: Sequence[Rated], offers: Sequence[Offered], titles: Mapping[str, str]
) -> Engagement:
    """`offers`: every choice between two activities offered to the learner."""
    live = [e for e in ordered(events) if e.struck is None]
    by_mode: dict[str, list[Event]] = {}
    for e in live:
        by_mode.setdefault(e.mode, []).append(e)
    rated: dict[str, list[int]] = {}
    for r in ratings:
        rated.setdefault(r.mode, []).append(r.value)
    offered: dict[str, int] = {}
    picked: dict[str, int] = {}
    for o in offers:
        if o.picked is None:  # left at the choice: they chose against neither, so it is no evidence either way
            continue
        for m in (o.first, o.second):
            offered[m] = offered.get(m, 0) + 1
        picked[o.picked] = picked.get(o.picked, 0) + 1
    prefs = preferences(ratings, [p for o in offers if (p := o.pick()) is not None])
    kinds: list[KindRow] = []
    for m in sorted(set(by_mode) | set(rated) | set(offered), key=lambda k: titles.get(k, k)):
        es = by_mode.get(m, [])
        v = rated.get(m, [])
        kinds.append(
            KindRow(
                mode=m,
                title=titles.get(m, m),
                rounds=len(es),
                right_first=sum(e.first_correct for e in es),
                median_seconds=round(statistics.median(_secs(e) for e in es), 1) if es else None,
                mean_tries=round(statistics.fmean(e.tries for e in es), 2) if es else None,
                left=sum(e.outcome == "left" for e in es),
                liked=v.count(1),
                okay=v.count(0),
                disliked=v.count(-1),
                offered=offered.get(m, 0),
                picked=picked.get(m, 0),
                preference=round(prefs.get(m, 0.0), 3),
            )
        )
    return Engagement(kinds=kinds, hypotheses=hypotheses(kinds, live))


def hypotheses(kinds: Sequence[KindRow], live: Sequence[Event]) -> list[Hypothesis]:
    """The spec's patterns (§11) that the log shows clearly enough to name."""
    out: list[Hypothesis] = []
    for k in kinds:
        recent = [e for e in live if e.mode == k.mode][-MIN_ROUNDS * 2 :]
        if len(recent) >= MIN_ROUNDS:
            share = sum(e.first_correct for e in recent) / len(recent)
            secs = statistics.median(_secs(e) for e in recent)
            tries = statistics.fmean(e.tries for e in recent)
            if share >= 0.8 and secs < QUICK_S:
                out.append(
                    Hypothesis(
                        code="quick_and_right",
                        mode=k.mode,
                        seen=f"{k.title}: right first time in {round(share * 100)}% of the last {len(recent)}, answered quickly.",
                        could_be="It is too easy, or it has become repetitive.",
                        try_="A new kind of round, or more choices in this one.",
                    )
                )
            elif share <= 0.4 and (tries >= 2 or secs >= SLOW_S):
                out.append(
                    Hypothesis(
                        code="stuck",
                        mode=k.mode,
                        seen=f"{k.title}: right first time in {round(share * 100)}% of the last {len(recent)}, with long pauses or many tries.",
                        could_be="Stuck on the skill, unsure what the round asks, or finding the taps hard.",
                        try_="Play one together and say what it asks, or fewer choices.",
                    )
                )
        rated = k.liked + k.okay + k.disliked
        if rated >= 3 and k.disliked * 2 > rated:
            out.append(
                Hypothesis(
                    code="disliked",
                    mode=k.mode,
                    seen=f"{k.title}: rated with the sad face {k.disliked} of {rated} times.",
                    could_be="It is not fun, it feels hard, or the faces were tapped at random.",
                    try_="Fewer of these for a while (the engine already offers it less), then try it again.",
                )
            )
        if k.offered >= 4 and k.picked * 4 <= k.offered and k.offered - k.picked >= 3:
            out.append(
                Hypothesis(
                    code="passed_over",
                    mode=k.mode,
                    seen=f"{k.title}: picked {k.picked} of the {k.offered} times it was offered.",
                    could_be="The other one looked more fun, or this one is not liked.",
                    try_="Nothing yet: the engine weighs it down a little, and the choice stays theirs.",
                )
            )
    late = _late_decline(live)
    if late is not None:
        out.append(late)
    return out


def _late_decline(live: Sequence[Event]) -> Hypothesis | None:
    """Fewer right in the second half of long sessions than in the first, over at least two of them."""
    sessions: dict[str, list[Event]] = {}
    for e in live:
        sessions.setdefault(e.session_id, []).append(e)
    long = [es for es in sessions.values() if len(es) >= 2 * MIN_ROUNDS]
    if len(long) < 2:
        return None
    early = [e.first_correct for es in long for e in es[: len(es) // 2]]
    late = [e.first_correct for es in long for e in es[len(es) // 2 :]]
    a, b = sum(early) / len(early), sum(late) / len(late)
    if a - b < 0.25:
        return None
    return Hypothesis(
        code="late_decline",
        mode=None,
        seen=f"Over {len(long)} longer sessions, {round(a * 100)}% right first time in the first half, {round(b * 100)}% in the second.",
        could_be="Tiredness, distraction, or rounds getting harder as the session goes on.",
        try_="Shorter sessions, or breaks more often (Settings, Sessions).",
    )
