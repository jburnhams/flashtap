"""Transfer: whether a skill shown in the kind of round it is practised in carries over to a second form of it (spec
§13: "progress when independent evidence is diverse ... and transfer probes pass"; §9 "holdout families for transfer
evaluation"; §11 "strong skill in one mechanic only": mechanic memorisation or representation-specific knowledge).

Every skill a practice kind assesses has one **transfer kind** (`rounds.TRANSFER`): the same skill asked another way
(the word heard with no picture to match, the group found for a number rather than the number for a group, every red
shape boxed rather than the one red shape tapped). It is held out of practice: Mixed and Play's list never offer it,
and the engine plays it only to check a skill it already rates as known from the practice kinds (engine/policy.py).
So a right answer there is not the same game remembered.

The rules, applied to the attempts `evidence.judge` already counts (so struck-out answers and answers held back for an
unshown confound play no part):

- A skill's **transfer answers** are its counted first answers, as the primary skill, in rounds of its transfer kind.
- It **passes** when its latest `PASS` transfer answers are all right (two in a row: a lucky pair among four tiles is
  1 in 16), and stops passing if a later one is missed: like every reporting state, it follows the latest evidence.
- It is **generalised** (`report.state_of`) only when it is independent, has passed, and has a right primary answer in
  a practice kind too, so the two forms are both in its evidence.

Nothing here moves an estimate: a transfer answer is an answer, counted by BKT like any other. Passing is a reporting
fact and a scheduling one (the engine stops checking a skill that has passed), never a second model.
"""

from collections.abc import Iterable, Sequence

from pydantic import BaseModel

from flashtap import rounds
from flashtap.learners.evidence import Event, Use
from flashtap.mechanics import Mode

PASS = 2  # the latest transfer answers that must all be right


class Transfer(BaseModel):
    """A skill's transfer evidence, for the grown-up: the kind that checks it, and how it went there."""

    mode: Mode  # the transfer kind
    name: str  # its name, as Play lists kinds ("Hear and find")
    tried: int  # counted first answers in it
    right: int  # of which right
    passed: bool  # the latest `PASS` all right


def is_transfer(e: Event, skill: str, role: str) -> bool:
    """Whether an attempt, as it bears on `skill` in `role`, is a transfer answer for that skill."""
    return role == "primary" and rounds.TRANSFER.get(skill) is not None and e.mode == rounds.TRANSFER[skill].value


def is_practice(e: Event) -> bool:
    """Whether an attempt is in a practice kind (any kind not held out), the first form a transfer is checked against."""
    try:
        return Mode(e.mode) not in rounds.HELD_OUT
    except ValueError:  # a kind no longer played: it was never a transfer kind
        return True


def passed(results: Sequence[bool]) -> bool:
    """Whether a run of transfer answers, oldest first, passes: the latest `PASS` all right."""
    return len(results) >= PASS and all(results[-PASS:])


def transfer(skill: str, counted: Iterable[Use]) -> Transfer | None:
    """A skill's transfer evidence from its counted uses, oldest first; None for a skill with no transfer kind."""
    mode = rounds.TRANSFER.get(skill)
    if mode is None:
        return None
    results = [u.event.first_correct for u in counted if is_transfer(u.event, skill, u.role)]
    return Transfer(
        mode=mode,
        name=rounds.TEMPLATES[mode].name,
        tried=len(results),
        right=sum(results),
        passed=passed(results),
    )
