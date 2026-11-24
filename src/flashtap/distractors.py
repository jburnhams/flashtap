"""Named distractor generators (spec §9): each wrong option a template offers comes from one of these, and says which.

A random wrong option tells little when it is tapped; a near number, a reversed numeral, a letter that is the right
one turned over or a sound one feature away tells which mistake was made, so evidence can be read as a misconception
(the packs' `maths.misconception.reversal_6_9`, `teen_reversal`; letter reversals b/d/p/q) rather than a slip. Each
generator returns candidates in order of preference; the template takes what it needs and fills the rest at random
(named `random`), so a round always fills.

The confusable and neighbour tables are drafts written here (the pack edges marked `src.flashtap_judgement` are the
same kind of judgement), to be checked with the phonics pack by someone who teaches it.
"""

import random
from collections.abc import Iterable, Sequence
from typing import TypeVar

T = TypeVar("T")  # not `def fill[T]`: Python 3.11 is still supported

NEAR_NUMBER = "near_number"
REVERSAL = "reversal"
CONFUSABLE_GRAPHEME = "confusable_grapheme"
PHONOLOGICAL_NEIGHBOUR = "phonological_neighbour"
SAME_CATEGORY = "same_category"
RANDOM = "random"


def near_numbers(n: int, low: int, high: int, rng: random.Random) -> list[int]:
    """Every other number in [low, high], nearest first; ties (n-1 and n+1) in a seeded order, so neither side is
    always first."""
    others = [k for k in range(low, high + 1) if k != n]
    rng.shuffle(others)
    return sorted(others, key=lambda k: abs(k - n))  # sorted is stable: the shuffle breaks the ties


def reversal(n: int) -> int | None:
    """The numeral a learner who reverses digits would tap: 6 for 9 and 9 for 6 (turned over), 21 for 12 (the order
    of two digits: "twelve" is heard ones-first in the teens). None when the reversal is the same number or has a
    leading zero."""
    if n in (6, 9):
        return 15 - n
    s = str(n)
    if len(s) == 2 and s[0] != s[1] and s[1] != "0":
        return int(s[::-1])
    return None


# Letters that are one shape turned or flipped (b d p q), or near it (m w, n u). Lower case, as phonics teaches.
CONFUSABLE: tuple[frozenset[str], ...] = (frozenset("bdpq"), frozenset("mw"), frozenset("nu"))


def confusable_graphemes(grapheme: str) -> list[str]:
    """Letters a learner could take for `grapheme` by its shape, in alphabetical order."""
    for group in CONFUSABLE:
        if grapheme in group:
            return sorted(group - {grapheme})
    return []


# Consonants as (voicing, place, manner), UK English, for the single-letter sounds of Phases 2 and 3. Two sounds are
# neighbours when they differ in one feature: /p/ and /b/ only in voicing, /m/ and /n/ only in place.
_CONSONANTS: dict[str, tuple[str, str, str]] = {
    "p": ("voiceless", "lips", "stop"),
    "b": ("voiced", "lips", "stop"),
    "t": ("voiceless", "ridge", "stop"),
    "d": ("voiced", "ridge", "stop"),
    "k": ("voiceless", "back", "stop"),
    "ɡ": ("voiced", "back", "stop"),  # noqa: RUF001 (IPA)
    "f": ("voiceless", "lip_teeth", "fricative"),
    "v": ("voiced", "lip_teeth", "fricative"),
    "s": ("voiceless", "ridge", "fricative"),
    "z": ("voiced", "ridge", "fricative"),
    "h": ("voiceless", "throat", "fricative"),
    "m": ("voiced", "lips", "nasal"),
    "n": ("voiced", "ridge", "nasal"),
    "l": ("voiced", "ridge", "lateral"),
    "r": ("voiced", "ridge", "approximant"),
    "w": ("voiced", "lips", "approximant"),
    "j": ("voiced", "palate", "approximant"),
}
# Short vowels next to each other in the mouth: the ones a learner hears as each other.
_VOWELS: dict[str, tuple[str, ...]] = {
    "æ": ("e", "ʌ"),
    "e": ("æ", "ɪ"),
    "ɪ": ("e",),
    "ɒ": ("ʌ",),
    "ʌ": ("ɒ", "æ"),
}


def phonological_neighbours(phoneme: str) -> list[str]:
    """Sounds one feature away from `phoneme` (IPA), in a fixed order."""
    if phoneme in _VOWELS:
        return list(_VOWELS[phoneme])
    me = _CONSONANTS.get(phoneme)
    if me is None:
        return []
    return [p for p, f in _CONSONANTS.items() if p != phoneme and sum(a != b for a, b in zip(f, me, strict=True)) == 1]


def fill(
    rng: random.Random, wanted: int, preferred: Iterable[tuple[T, str]], pool: Sequence[T], exclude: set[T]
) -> list[tuple[T, str]]:
    """`wanted` distinct distractors: the `preferred` (value, generator) pairs first, in order, then random picks from
    `pool`, each named `random`. Values in `exclude` (the answer, and anything else that would also be right) are never
    taken."""
    out: list[tuple[T, str]] = []
    seen = set(exclude)
    for v, why in preferred:
        if len(out) == wanted:
            break
        if v not in seen:
            out.append((v, why))
            seen.add(v)
    rest = [v for v in pool if v not in seen]
    out += [(v, RANDOM) for v in rng.sample(rest, min(wanted - len(out), len(rest)))]
    return out
