"""From the event log to evidence per skill: which attempts count for which skill, and why the others do not.

This is the one place those rules live; the estimators only fold what it counts, and the Learner screen shows its
reasons beside each attempt (the spec's "evidence provenance", §15). The rules, from the round's Q-matrix (§8):

- Only the first answer is judged. A second tap after a wrong one is teaching, not an independent assessment (§10).
- **Primary** skill: a right first answer counts for it, and so does a wrong one, unless a **confound** of the same
  round has not been shown yet: a wrong answer in Counting may be a numeral the learner cannot read yet, not a miscount,
  so it is held back ("could be ...") until that skill has been shown. Once shown, later wrong answers count.
- **Secondary** and **confound** skills: a right first answer counts (getting it right needed them); a wrong one does
  not, since the round was not written to tell which part went wrong.
- A skill is *shown* once it has one counted right answer, in any role.
- A struck-out attempt (a tombstone) counts for nothing and touches nothing.

Attempts are taken oldest first by (presented_at, event_id), so the same log in any storage order gives the same
evidence: the replay test shuffles it to prove so.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field


class SkillUse(BaseModel):
    skill: str
    role: str  # primary, secondary or confound


class Event(BaseModel):
    """An attempt as the log keeps it: what the database holds and what an export carries, so a replay from either
    goes through the same code."""

    event_id: str
    session_id: str
    mode: str
    version: int
    choices: int
    seed: int
    # The content packs the round drew from, {pack: version} (rounds.content_of). Empty in an export from before
    # 0.7.0, when every pack was at version 1: a rebuild then takes the packs as they are.
    content: dict[str, int] = Field(default_factory=dict[str, int])
    mechanic: str
    options: int
    skills: list[SkillUse]
    asked: str
    presented_at: AwareDatetime
    answered_at: AwareDatetime
    first_answer: dict[str, object]
    first_correct: bool
    tries: int
    outcome: str
    struck: str | None = None  # the tombstone's reason, when a grown-up struck the attempt out
    # For replaying the adaptive engine (src/flashtap/engine/replay.py): what the server knew when it chose a round is
    # the attempts it had received by then, struck or not as they stood then. All three are absent from an export
    # made before 0.6.0; a replay then takes the answer time as the receipt and the strike as made at the start.
    received_at: AwareDatetime | None = None
    struck_at: AwareDatetime | None = None
    decision_id: str | None = None  # the engine's choice this round answered (POST /api/v1/sessions/{id}/next)


@dataclass(frozen=True)
class Observation:
    """One counted first answer for one skill: all an estimator sees."""

    event_id: str
    at: datetime
    correct: bool
    options: int  # tiles offered, for the chance of a lucky tap; 0 for an arrangement
    mechanic: str
    role: str


@dataclass(frozen=True)
class Use:
    """One attempt as it bears on one skill, counted or not, with the reason when not: a row of provenance."""

    event: Event
    skill: str
    role: str
    counted: bool
    why: str  # empty when counted


def ordered(events: Iterable[Event]) -> list[Event]:
    return sorted(events, key=lambda e: (e.presented_at, e.event_id))


def judge(e: Event, shown: set[str], names: Mapping[str, str] | None = None) -> list[Use]:
    """One attempt's uses, one per skill it names, given the skills `shown` so far; adds to `shown` when it was right.
    The one place the rules above are applied: `uses` folds a whole log through it, and the adaptive engine folds one
    attempt at a time (src/flashtap/engine/model.py), so the two can never count differently."""
    titles = names or {}
    if e.struck is not None:
        return [Use(e, s.skill, s.role, False, f"struck out: {e.struck}") for s in e.skills]
    unshown = [s.skill for s in e.skills if s.role == "confound" and s.skill not in shown]
    out: list[Use] = []
    for s in e.skills:
        if e.first_correct:
            out.append(Use(e, s.skill, s.role, True, ""))
        elif s.role != "primary":
            out.append(
                Use(
                    e, s.skill, s.role, False, "a wrong answer counts only for the skill the round is written to assess"
                )
            )
        elif unshown:
            why = "could be " + " or ".join(titles.get(c, c) for c in unshown) + ", not yet shown"
            out.append(Use(e, s.skill, s.role, False, why))
        else:
            out.append(Use(e, s.skill, s.role, True, ""))
    if e.first_correct:
        shown.update(s.skill for s in e.skills)
    return out


def uses(events: Iterable[Event], titles: Mapping[str, str] | None = None) -> dict[str, list[Use]]:
    """Every skill's uses, oldest first. `titles` names skills in the reasons (a skill's id otherwise)."""
    shown: set[str] = set()
    out: dict[str, list[Use]] = {}
    for e in ordered(events):
        for u in judge(e, shown, titles):
            out.setdefault(u.skill, []).append(u)
    return out


def observations(skill_uses: Iterable[Use]) -> list[Observation]:
    return [
        Observation(
            u.event.event_id, u.event.presented_at, u.event.first_correct, u.event.options, u.event.mechanic, u.role
        )
        for u in skill_uses
        if u.counted
    ]
