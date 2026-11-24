"""Which misconception a wrong option would show (spec §3 `misconception_of`, §9 "misconception-targeted"
distractors, §16 "misconception discrimination").

Every wrong option already names the generator that chose it (`flashtap.distractors`). Some of those, in some kinds of
round, are exactly the tap a named misconception in the packs predicts: a 9 for six is `maths.misconception.reversal_6_9`
("taps 9 for six or 6 for nine"), a d for b is `literacy.misconception.mirror_letters`, a count one or two out is
`maths.misconception.one_to_one_slip`. `traps` lists, for one round, the options that would show each one, so that an
attempt can store, at the moment it is judged, what its round offered and what the tap showed (Attempt.traps): one
wrong answer is a slip, a pattern of them where chance would give few is a hypothesis worth checking
(`learners/misconceptions.py`).

The rules below are a draft, like the distractor tables they read (marked `src.flashtap_judgement` in the packs where
they are a judgement): a near number is read as a counting slip only in Counting, where it is the count that is off,
not in Quick look (a near miss there is a glance, not a skipped object) or Missing number (the number before or after
is the slip that kind was written to catch, not a misconception). A look-alike letter shows mirror letters only among
b, d, p and q; m for w and n for u are kept as the distractor's name and nothing more. Generators that no misconception
predicts (`phonological_neighbour`, `same_category`, `random`) show none. A placing round shows none yet: its first
answer is a whole arrangement, and reading one mistake out of it is a rule still to write.

`PROBES` names the kinds of round, and the lowest step of each, that can offer each trap: the engine asks for one of
those to check a suspicion (engine/policy.py), and a test walks seeds to prove each can.
"""

from collections.abc import Mapping

from flashtap import distractors as dx
from flashtap.mechanics import PLACE, Mode, Option, Round

REVERSAL_6_9 = "maths.misconception.reversal_6_9"
TEEN_REVERSAL = "maths.misconception.teen_reversal"
MIRROR_LETTERS = "literacy.misconception.mirror_letters"
ONE_TO_ONE = "maths.misconception.one_to_one_slip"
NAMED = (REVERSAL_6_9, TEEN_REVERSAL, MIRROR_LETTERS, ONE_TO_ONE)  # every id here is in the packs (test_mistakes.py)

MIRROR = frozenset("bdpq")
COUNT_SLIP = 2  # a count this far out or nearer reads as an object skipped or counted twice

# The kinds that can offer each trap, with the easiest step that can: 6 and 9 need numbers to 8 at least (step 2 of
# Counting, step 1 of Missing number); Quick look never goes past 5. Teen reversal is in none yet: no kind offers
# numbers past 20, and 12's reversal is 21. A b, d, p or q is in every step of the letter kinds.
PROBES: Mapping[str, Mapping[Mode, int]] = {
    REVERSAL_6_9: {Mode.COUNTING: 2, Mode.MISSING: 1},
    TEEN_REVERSAL: {},
    MIRROR_LETTERS: {Mode.LETTERS: 0, Mode.LISTEN: 0, Mode.SOUNDS: 0},
    ONE_TO_ONE: {Mode.COUNTING: 0},
}


def _number(o: Option) -> int | None:
    return int(o.word) if o.word.isdigit() else None


def _letter(r: Round, o: Option) -> str:
    """The letter an option stands for: its word's first letter in Letters (the tile is a picture), else the word."""
    return o.word[:1].lower() if r.mode is Mode.LETTERS else o.word


def shows(r: Round, o: Option) -> str | None:
    """The misconception tapping `o` in round `r` would show, or None (the right option, or a plain slip)."""
    if o.correct:
        return None
    right = next(x for x in r.options if x.correct)
    if o.distractor == dx.REVERSAL:
        a, b = _number(right), _number(o)
        return REVERSAL_6_9 if {a, b} == {6, 9} else TEEN_REVERSAL
    if o.distractor == dx.CONFUSABLE_GRAPHEME and {_letter(r, right), _letter(r, o)} <= MIRROR:
        return MIRROR_LETTERS
    if o.distractor == dx.NEAR_NUMBER and r.mode is Mode.COUNTING:
        a, b = _number(right), _number(o)
        if a is not None and b is not None and abs(a - b) <= COUNT_SLIP:
            return ONE_TO_ONE
    return None


def traps(r: Round) -> dict[str, list[str]]:
    """Each misconception the round's wrong options could show, with those options' ids in the round's order; empty
    for a placing round or one with no such option."""
    if r.mechanic in PLACE:
        return {}
    out: dict[str, list[str]] = {}
    for o in r.options:
        m = shows(r, o)
        if m is not None:
            out.setdefault(m, []).append(o.id)
    return out
