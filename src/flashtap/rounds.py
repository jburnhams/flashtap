"""Rounds: the kinds of round, what each one is (its template), and how a round is built and checked.

A template is a kind of round at a version: its mechanic, the skills it gives evidence on and in what role (the spec's
Q-matrix, §8), and the function that builds its body (`flashtap.kinds`). A round is a pure function of (kind, version,
choices, seed): the same four give the same round, so a round a learner saw can be rebuilt exactly and a test can walk
thousands of seeds. Raise a template's `version` whenever its function would give a different round for a seed it
gave before; only the current version of each is kept, and asking for another is refused rather than answered
differently. The server picks a seed when the client sends none and returns it in the round.

`mechanics.check` refuses a round whose answer is not one and unmistakable, and `generate` runs it on every round
served. The 0.1 generators broke this in several ways (two red shapes for "Which one is red?", Counting looping above
ten choices, tiles printing their own names); tests/unit/test_rounds.py walks 1,000 seeds of every template.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass

from flashtap.kinds import Body, choose, place
from flashtap.mechanics import (
    PLACE,
    SEED_LIMIT,
    InvalidRound,
    Mechanic,
    Mode,
    Option,
    Piece,
    Place,
    QRole,
    Round,
    SkillRole,
    check,
)

__all__ = [
    "MAX_CHOICES",
    "MIN_CHOICES",
    "MODE_NAMES",
    "MODE_SKILLS",
    "PLAYABLE",
    "SEED_LIMIT",
    "TEMPLATES",
    "InvalidRound",
    "Mechanic",
    "Mode",
    "Option",
    "Piece",
    "Place",
    "Round",
    "Template",
    "check",
    "generate",
    "tries_allowed",
]

MIN_CHOICES = 2
MAX_CHOICES = 8  # the smallest pool a choose kind draws from (Colours: the shapes not of one colour) still fills 8

P, S, C = QRole.PRIMARY, QRole.SECONDARY, QRole.CONFOUND


@dataclass(frozen=True)
class Template:
    mode: Mode
    version: int
    mechanic: Mechanic
    name: str
    description: str  # what the learner does, for the list a grown-up picks from
    skills: tuple[tuple[str, QRole], ...]
    build: Callable[[random.Random, int], Body]


TEMPLATES: dict[Mode, Template] = {
    t.mode: t
    for t in (
        Template(
            Mode.MATCHING, 1, Mechanic.SELECT_ONE, "Matching", "Find the animal, food or vehicle that was named",
            (("language.vocabulary.receptive", P),), choose.matching,
        ),
        Template(
            Mode.COLOURS, 1, Mechanic.SELECT_ONE, "Colours", "Find the shape of the named colour",
            (("language.vocabulary.colours", P),), choose.colours,
        ),
        Template(
            Mode.SHAPES, 1, Mechanic.SELECT_ONE, "Shapes", "Find the named coloured shape",
            (("maths.geometry.name_2d", P), ("language.vocabulary.colours", C)), choose.shapes,
        ),
        Template(
            Mode.LETTERS, 1, Mechanic.SELECT_ONE, "Letters", "Find the picture whose word starts with the letter",
            (("literacy.gpc.initial_letter", P), ("literacy.phonemic.initial_sound", S), ("language.vocabulary.receptive", C)),
            choose.letters,
        ),
        Template(
            Mode.COUNTING, 1, Mechanic.SELECT_ONE, "Counting", "Count the pictures and tap the number",
            (("maths.counting.objects", P), ("maths.cardinality.last_number", S), ("maths.numerals.recognise", C)),
            choose.counting,
        ),
        Template(
            Mode.MISSING, 1, Mechanic.FILL_MISSING, "Missing number", "Find the number missing from a run",
            (("maths.verbal_count.one_more", P), ("maths.verbal_count.forwards", S), ("maths.numerals.recognise", C)),
            choose.missing,
        ),
        Template(
            Mode.QUICK_LOOK, 1, Mechanic.BRIEF_EXPOSURE, "Quick look", "See a few pictures for a moment and say how many",
            (("maths.subitising.perceptual", P), ("maths.numerals.recognise", C)), choose.quick_look,
        ),
        Template(
            Mode.LISTEN, 1, Mechanic.AUDIO_RESPOND, "Listen", "Hear a word and tap the letter it starts with",
            (("literacy.gpc.grapheme_from_sound", P), ("literacy.phonemic.initial_sound", S)), choose.listen,
        ),
        Template(
            Mode.GIVE, 1, Mechanic.GIVE_N, "Give a number", "Put the asked-for number of pictures in the basket",
            (("maths.cardinality.give_n", P), ("maths.counting.one_to_one", C)), place.give,
        ),
        Template(
            Mode.ORDER, 1, Mechanic.SEQUENCE, "Order", "Put numbers in order, smallest first",
            (("maths.comparison.order", P), ("maths.numerals.recognise", C)), place.order,
        ),
        Template(
            Mode.CAPITALS, 1, Mechanic.MATCH_PAIRS, "Capitals", "Put each small letter on its capital",
            (("literacy.letters.case_match", P), ("literacy.letters.identify", S)), place.capitals,
        ),
        Template(
            Mode.SORT_SOUNDS, 1, Mechanic.SORT, "Sort by sound", "Put pictures with the letter of their first sound",
            (("literacy.phonemic.initial_sound", P), ("literacy.gpc.sound_from_grapheme", S), ("language.vocabulary.receptive", C)),
            place.sort_sounds,
        ),
    )
}  # fmt: skip

PLAYABLE = tuple(TEMPLATES)
# What each kind asks, for the list a person picks from (GET /api/modes), Mixed last.
MODE_NAMES: dict[Mode, tuple[str, str]] = {
    **{m: (t.name, t.description) for m, t in TEMPLATES.items()},
    Mode.MIXED: ("Mixed", "A different kind of round each time"),
}
# The skills each kind gives evidence on (any role), for the Content screen; tests/unit/test_content.py checks they exist.
MODE_SKILLS: dict[Mode, tuple[str, ...]] = {m: tuple(s for s, _ in t.skills) for m, t in TEMPLATES.items()}


def generate(mode: Mode, choices: int, seed: int | None = None, version: int | None = None) -> Round:
    """One checked round. `seed` None picks one (returned in the round); the same mode, choices, seed and version give
    the same round, and the round's own (mode, version, choices, seed) rebuild it. `version` None is the current one; any other is refused (only the current one is kept)."""
    if not MIN_CHOICES <= choices <= MAX_CHOICES:
        raise ValueError(f"choices must be between {MIN_CHOICES} and {MAX_CHOICES}, not {choices}")
    if seed is None:
        seed = random.randrange(SEED_LIMIT)
    played = mode
    if mode is Mode.MIXED:
        # Mixed picks the kind and then the round's own seed from `seed`, so the round carries a (kind, seed) that
        # rebuilds it without going through Mixed. (0.2 drew the round from the same generator after picking the kind,
        # so a Mixed round's reported kind and seed rebuilt a different round.)
        pick = random.Random(seed)
        played = pick.choice(PLAYABLE)
        seed = pick.randrange(SEED_LIMIT)
    rng = random.Random(seed)
    t = TEMPLATES[played]
    if version is not None and version != t.version:
        raise ValueError(f"{played} is at version {t.version}; version {version} is not kept")
    b = t.build(rng, choices)
    return check(
        Round(
            mode=played,
            version=t.version,
            choices=choices,
            seed=seed,
            mechanic=t.mechanic,
            skills=[SkillRole(skill=s, role=r) for s, r in t.skills],
            prompt=b.prompt,
            say=b.say or b.prompt,
            show=b.show,
            exposure_ms=b.exposure_ms,
            options=b.options,
            answer=b.answer,
            pieces=b.pieces,
            places=b.places,
            done_feedback=b.done_feedback,
        )
    )


def tries_allowed(tries: int, r: Round) -> int | None:
    """How many tries a round allows before it counts as missed: None for no limit (tries 0). A choose round counts
    taps, at most one fewer than its options so the last one is never a give-away; a place round counts checks."""
    if tries <= 0:
        return None
    if r.mechanic in PLACE:
        return tries
    return max(1, min(tries, len(r.options) - 1))
