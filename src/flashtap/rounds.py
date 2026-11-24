"""Rounds: the kinds of round, what each one is (its template), and how a round is built and checked.

A template is a kind of round at a version: its mechanic, the skills it gives evidence on and in what role (the spec's
Q-matrix, §8), and the function that builds its body (`flashtap.kinds`). A round is a pure function of (kind, version,
choices, seed): the same four give the same round, so a round a learner saw can be rebuilt exactly and a test can walk
thousands of seeds. Raise a template's `version` whenever its function would give a different round for a seed it
gave before; only the current version of each is kept, and asking for another is refused rather than answered
differently. The server picks a seed when the client sends none and returns it in the round.

The template's code is half of a round; the content packs it draws from are the other half (the words and pictures, the
phonics inventory, the skills it names). A round carries the versions of those packs (`content`, from `content_of`),
an attempt stores them, and a rebuild names them: a round made from packs since changed is refused, as a template
version no longer kept is, rather than rebuilt from today's words and judged against the wrong round (spec §14,
"record generator seed, source versions"; docs/content.md).

`mechanics.check` refuses a round whose answer is not one and unmistakable, and `generate` runs it on every round
served. The 0.1 generators broke this in several ways (two red shapes for "Which one is red?", Counting looping above
ten choices, tiles printing their own names); tests/unit/test_rounds.py walks 1,000 seeds of every template.
"""

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache

from flashtap import content
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
    "PICTURES",
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
    "content_of",
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
        Template(
            Mode.SOUNDS, 1, Mechanic.AUDIO_RESPOND, "Sounds", "Hear a sound on its own and tap the letters that make it",
            (("literacy.gpc.grapheme_from_sound", P),), choose.sounds,
        ),
    )
}  # fmt: skip

PLAYABLE = tuple(TEMPLATES)
# One picture per kind, for the tiles a learner picks between when offered a choice of two (engine/policy.py): what
# the round looks like, since a learner who cannot read yet picks by the picture and the spoken name.
PICTURES: dict[Mode, str] = {
    Mode.MATCHING: "\U0001f404",  # cow
    Mode.COLOURS: "\U0001f3a8",  # palette
    Mode.SHAPES: "\U0001f53a",  # red triangle
    Mode.LETTERS: "\U0001f524",  # abc
    Mode.COUNTING: "\U0001f522",  # 1234
    Mode.MISSING: "\u2753",  # question mark
    Mode.QUICK_LOOK: "\U0001f440",  # eyes
    Mode.LISTEN: "\U0001f442",  # ear
    Mode.GIVE: "\U0001f9fa",  # basket
    Mode.ORDER: "\U0001fa9c",  # ladder
    Mode.CAPITALS: "\U0001f520",  # ABCD
    Mode.SORT_SOUNDS: "\U0001f5c2\ufe0f",  # card index dividers
    Mode.SOUNDS: "\U0001f50a",  # speaker
}
# What each kind asks, for the list a person picks from (GET /api/modes), Mixed last.
MODE_NAMES: dict[Mode, tuple[str, str]] = {
    **{m: (t.name, t.description) for m, t in TEMPLATES.items()},
    Mode.MIXED: ("Mixed", "A different kind of round each time"),
}
# The skills each kind gives evidence on (any role), for the Content screen; tests/unit/test_content.py checks they exist.
MODE_SKILLS: dict[Mode, tuple[str, ...]] = {m: tuple(s for s, _ in t.skills) for m, t in TEMPLATES.items()}


@cache
def _content(mode: Mode) -> tuple[tuple[str, int], ...]:
    t = TEMPLATES[mode]
    named = {s for s, _ in t.skills}
    # Every kind counts the packs behind the lexicon (words and the phonics inventory) as drawn from, even the two that
    # only use numbers (Missing number, Order): over-claiming only refuses a rebuild that would have matched, while
    # under-claiming would judge an old answer against a changed round, which is the bug this guards against.
    return tuple(
        sorted(
            (p.pack, p.version)
            for p in content.load().packs
            if p.words or p.phonics or any(s.id in named for s in p.skills)
        )
    )


def content_of(mode: Mode) -> dict[str, int]:
    """The packs a round of this kind draws from, each with its version: `{"words": 1, ...}`. Read from the packs on
    first use, not at import, so a broken pack still lets `flashtap content check` start and name the problem."""
    return dict(_content(mode))


def _versions(c: Mapping[str, int]) -> str:
    return ", ".join(f"{k}@{v}" for k, v in sorted(c.items())) or "no packs"


def generate(
    mode: Mode,
    choices: int,
    seed: int | None = None,
    version: int | None = None,
    content: Mapping[str, int] | None = None,
) -> Round:
    """One checked round. `seed` None picks one (returned in the round); the same mode, choices, seed, version and
    content give the same round, and the round's own (mode, version, choices, seed, content) rebuild it. `version` and
    `content` None are the current ones; any other is refused (only the current template and packs are kept)."""
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
    now = content_of(played)
    if content is not None and dict(content) != now:
        raise ValueError(
            f"{played} was made from {_versions(content)}; the packs are now {_versions(now)} and the earlier ones are "
            "not kept"
        )
    b = t.build(rng, choices)
    return check(
        Round(
            mode=played,
            version=t.version,
            content=now,
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
