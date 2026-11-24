"""Misconceptions from wrong first answers (spec §10 "confusion patterns, active misconceptions"; §16 "misconception
discrimination"): when a learner's wrong taps land on the option a named misconception predicts more often than chance
would put them there, that misconception is a hypothesis worth checking, never a label.

Each attempt stores what its round could show (`Event.traps`, from `flashtap.mistakes` when it was judged) and the
option first tapped, so the tally needs no round rebuilt. For each misconception, over the learner's first answers to
rounds that offered it (struck rounds and older attempts with nothing stored count for nothing):

- `offered`: rounds that had an option showing it; `wrong`: of those, answered wrong first; `shown`: the wrong first
  answers that were that option.
- **Chance**: a wrong first answer is taken, under the "just a slip" hypothesis, to land on any wrong option alike, so
  it lands on the trap with chance (trap options) / (wrong options). `expected` is the sum over the wrong answers, and
  the chance of seeing `shown` or more by luck is the upper tail of that Poisson binomial (`tail`).
- **Status**: `not_seen` (offered, never shown); `suspected` when shown at least `MIN_SHOWN` times and the tail is at
  most `ALPHA`; `cleared` once, after its last showing, it was offered `CLEAR` times running and answered right each
  time; else `unclear` (shown, but no more than luck explains yet). Cleared beats suspected: what they do now counts.

Like `evidence.judge`, this is one fold shared by the Learner screen (`report`) and the engine (`Tally.observe` inside
`engine/model.Knowledge`), so the two never disagree, and it is computed from the log on every read, so a rebuild
gives the same. Every threshold is a first guess, to be fitted once there are real answers (§0).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from flashtap import mistakes
from flashtap.content.model import Misconception
from flashtap.learners.evidence import Event, ordered

MIN_SHOWN = 2  # one tap on the trap is a slip, whatever the odds
ALPHA = 0.05  # at most this chance of `shown` or more by luck to call it suspected
CLEAR = 3  # offered and answered right this many times running after its last showing


class MisconceptionStatus(StrEnum):
    NOT_SEEN = "not_seen"
    UNCLEAR = "unclear"
    SUSPECTED = "suspected"
    CLEARED = "cleared"


def tail(chances: Sequence[float], at_least: int) -> float:
    """The chance that at least `at_least` of independent events with these chances happen (a Poisson binomial)."""
    if at_least <= 0:
        return 1.0
    dist = [1.0]  # dist[k]: the chance of exactly k so far
    for p in chances:
        dist = [
            (dist[k] if k < len(dist) else 0.0) * (1 - p) + (dist[k - 1] * p if k > 0 else 0.0)
            for k in range(len(dist) + 1)
        ]
    return min(1.0, sum(dist[at_least:]))


@dataclass
class Tally:
    """One misconception's evidence for one learner, folded oldest first."""

    offered: int = 0
    wrong: int = 0
    shown: int = 0
    chances: list[float] = field(default_factory=list[float])  # one per wrong answer: its chance of landing on it
    right_since: int = 0  # offered and right first time, running, since it was last shown
    last_shown: datetime | None = None
    skills: set[str] = field(default_factory=set[str])  # the skills the rounds that showed it were written to assess

    @property
    def expected(self) -> float:
        return sum(self.chances)

    @property
    def status(self) -> MisconceptionStatus:
        if self.shown == 0:
            return MisconceptionStatus.NOT_SEEN
        if self.right_since >= CLEAR:
            return MisconceptionStatus.CLEARED
        if self.shown >= MIN_SHOWN and tail(self.chances, self.shown) <= ALPHA:
            return MisconceptionStatus.SUSPECTED
        return MisconceptionStatus.UNCLEAR

    @property
    def open(self) -> bool:
        """Worth checking with a round that offers it: shown, and not cleared since."""
        return self.status in (MisconceptionStatus.SUSPECTED, MisconceptionStatus.UNCLEAR)


def observe(tallies: dict[str, Tally], e: Event) -> None:
    """Fold one attempt into `tallies`, by misconception id."""
    if e.struck is not None or not e.traps:
        return
    showed = e.showed()
    primary = [s.skill for s in e.skills if s.role == "primary"]
    for m, ids in sorted(e.traps.items()):
        t = tallies.setdefault(m, Tally())
        t.offered += 1
        if e.first_correct:
            t.right_since += 1
            continue
        t.wrong += 1
        t.chances.append(len(ids) / max(1, e.options - 1))
        t.right_since = 0
        if showed == m:
            t.shown += 1
            t.last_shown = e.presented_at
            t.skills.update(primary)


def tallies(events: Iterable[Event]) -> dict[str, Tally]:
    out: dict[str, Tally] = {}
    for e in ordered(events):
        observe(out, e)
    return out


class MisconceptionReport(BaseModel):
    """One misconception as the evidence stands, for a grown-up: a hypothesis with what it rests on."""

    id: str
    title: str
    signs: str  # what a learner who has it does, from the packs
    probe: str  # a round that tells it from a slip, from the packs, for a grown-up to try
    checks: bool  # whether rounds the engine chooses offer its trap, to check it (mistakes.PROBES)
    skills: list[str]  # the skills it bears on: the packs' list, then those of the rounds that showed it
    status: MisconceptionStatus
    offered: int
    wrong: int
    shown: int
    expected: float  # how many of the wrong answers luck alone would put on it
    last_shown: datetime | None


ORDER = (
    MisconceptionStatus.SUSPECTED,
    MisconceptionStatus.UNCLEAR,
    MisconceptionStatus.CLEARED,
    MisconceptionStatus.NOT_SEEN,
)


def report(events: Iterable[Event], known: Mapping[str, Misconception]) -> list[MisconceptionReport]:
    """Every misconception a round has offered this learner, suspected first. One the packs no longer name is kept
    under its id: the attempts that showed it are still the learner's."""
    out: list[MisconceptionReport] = []
    for m, t in tallies(events).items():
        info = known.get(m)
        skills = list(info.skills) if info is not None else []
        out.append(
            MisconceptionReport(
                id=m,
                title=info.title if info is not None else m,
                signs=info.signs if info is not None else "",
                probe=info.probe if info is not None else "",
                checks=bool(mistakes.PROBES.get(m)),
                skills=[*skills, *sorted(t.skills - set(skills))],
                status=t.status,
                offered=t.offered,
                wrong=t.wrong,
                shown=t.shown,
                expected=round(t.expected, 2),
                last_shown=t.last_shown,
            )
        )
    return sorted(out, key=lambda r: (ORDER.index(r.status), r.title))


def suspected(reports: Iterable[MisconceptionReport]) -> dict[str, list[str]]:
    """The titles of the misconceptions suspected, by each skill they bear on."""
    out: dict[str, list[str]] = {}
    for r in reports:
        if r.status is MisconceptionStatus.SUSPECTED:
            for s in r.skills:
                out.setdefault(s, []).append(r.title)
    return out
