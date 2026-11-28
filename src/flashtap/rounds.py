"""Rounds: the kinds of round, what each one is (its template), and how a round is built and checked.

A template is a kind of round at a version: its mechanic, the skills it gives evidence on and in what role (the spec's
Q-matrix, §8), the function that builds its body (`flashtap.kinds`) and its steps of difficulty (`levels`, below). A
round is a pure function of (kind, version, choices, seed, level): the same five give the same round, so a round a
learner saw can be rebuilt exactly and a test can walk thousands of seeds. Raise a template's `version` whenever its function would give a different round for a seed it
gave before; only the current version of each is kept, and asking for another is refused rather than answered
differently. The server picks a seed when the client sends none and returns it in the round.

The template's code is half of a round; the content packs it draws from are the other half (the words and pictures, the
phonics inventory, the skills it names). A round carries the versions of those packs (`content`, from `content_of`),
an attempt stores them, and a rebuild names them: a round made from packs since changed is refused, as a template
version no longer kept is, rather than rebuilt from today's words and judged against the wrong round (spec §14,
"record generator seed, source versions"; docs/content.md).

**Steps of difficulty** (spec §6, "shared difficulty dimensions": content and distractors). Each template has a short
ladder of `Level`s, easiest first: how many options or pieces a round lays out and, for the number kinds, the largest
number in play (`top`, inside the skill's `number_range` in the packs); for a quick look (version 2, 0.21.0) also how
long its pictures show and how many looks again it allows. The adaptive engine chooses the step from the
learner's answers (engine/model.py `Stair`); a round played by hand has no step (`level` None) and is built from the
grown-up's number of choices and the kind's fixed range, exactly as before steps existed, so every round made before
0.11.0 rebuilds unchanged and no template version was raised. A round with a step carries it, and its attempt records
it, so it rebuilds from (kind, version, choices, seed, level); its `choices` must be its step's.

`mechanics.check` refuses a round whose answer is not one and unmistakable, and `generate` runs it on every round
served. The 0.1 generators broke this in several ways (two red shapes for "Which one is red?", Counting looping above
ten choices, tiles printing their own names); tests/unit/test_rounds.py walks 1,000 seeds of every template.
"""

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache

from flashtap import content
from flashtap.kinds import Body, choose, place, starter
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
    "HELD_OUT",
    "MAX_CHOICES",
    "MIN_CHOICES",
    "MODE_NAMES",
    "MODE_SKILLS",
    "PICTURES",
    "PLAYABLE",
    "PRACTICE",
    "SEED_LIMIT",
    "TEMPLATES",
    "TRANSFER",
    "InvalidRound",
    "Level",
    "Mechanic",
    "Mode",
    "Option",
    "Piece",
    "Place",
    "Round",
    "Template",
    "at_level",
    "check",
    "content_of",
    "generate",
    "tries_allowed",
]

MIN_CHOICES = 2
MAX_CHOICES = 8  # the smallest pool a choose kind draws from (Colours: the shapes not of one colour) still fills 8

P, S, C = QRole.PRIMARY, QRole.SECONDARY, QRole.CONFOUND


@dataclass(frozen=True)
class Level:
    """One step of a template's difficulty: `choices` options or pieces and, for a number kind, numbers up to `top`.
    `says` is the step in a grown-up's words, for the engine's reasons ("numbers to 10, 4 to pick from")."""

    choices: int
    says: str
    top: int | None = None
    # A brief exposure's (0.21.0): how long the pictures show and how many looks again the learner may ask for. None
    # keeps the body's own (a kind that hides nothing).
    exposure_ms: int | None = None
    peeks: int = 0


Build = Callable[[random.Random, int, int | None], Body]


def _plain(f: Callable[[random.Random, int], Body]) -> Build:
    """A kind with no number range: its steps change only how many options it lays out."""
    return lambda rng, choices, _top: f(rng, choices)


def _picks(*ns: int) -> tuple[Level, ...]:
    return tuple(Level(n, f"{n} to pick from") for n in ns)


def _numbers(*steps: tuple[int, int]) -> tuple[Level, ...]:
    return tuple(Level(n, f"numbers to {top}, {n} to pick from", top) for n, top in steps)


def _looks(*steps: tuple[int, int, int, int]) -> tuple[Level, ...]:
    """A quick look's steps: (choices, top, milliseconds shown, looks again). The owner (2026-11-28) asked for the
    time shown and the free looks again to be levers the engine sets from success, beside the numbers and tiles."""

    def says(n: int, top: int, ms: int, peeks: int) -> str:
        again = "no looks again" if not peeks else "1 look again" if peeks == 1 else f"{peeks} looks again"
        return f"numbers to {top}, {n} to pick from, {ms / 1000:g} second{'' if ms == 1000 else 's'} to look, {again}"

    return tuple(Level(n, says(n, top, ms, peeks), top, ms, peeks) for n, top, ms, peeks in steps)


# Easiest first: more time and looks again before more numbers, then less time. Each step changes one or two levers.
QUICK_LOOK_STEPS = _looks(
    (3, 3, 3000, 2), (3, 3, 2000, 1), (4, 5, 2500, 1), (4, 5, 1500, 1), (4, 5, 1500, 0), (6, 5, 1000, 0)
)


@dataclass(frozen=True)
class Template:
    mode: Mode
    version: int
    mechanic: Mechanic
    name: str
    description: str  # what the learner does, for the list a grown-up picks from
    skills: tuple[tuple[str, QRole], ...]
    build: Build
    levels: tuple[Level, ...]  # easiest first; the engine's steps (the grown-up's rounds have none)
    # A transfer kind (0.13.0): a second form of its primary skill, held out of practice. The engine plays it only to
    # check that a skill known in its own kind carries over (engine/policy.py), Mixed never picks it, and Play's list
    # leaves it out; its answers are the skill's transfer evidence (learners/transfer.py).
    held_out: bool = False


TEMPLATES: dict[Mode, Template] = {
    t.mode: t
    for t in (
        # First steps (0.14.0, packs/starter.toml): the easiest rounds, first in every list, where a new learner
        # begins. Two tiles at the first step, never more than four: the engine opens the other kinds only once these
        # are shown (engine/policy.py, "Opening rounds by success").
        # 0.15.0: the very first rounds are numbers to five, colours, shapes and animals (the owner's words), so Same
        # picture shows animals only (version 2) and Same shape joins; Same letter stays in this list but waits on the
        # first words (engine/policy.py, `FIRST_WORDS`).
        Template(
            Mode.SAME_PICTURE, 2, Mechanic.SELECT_ONE, "Same animal", "See an animal and tap the same one",
            (("language.matching.picture", P),), _plain(starter.same_picture), _picks(2, 3, 4),
        ),
        Template(
            Mode.SAME_COLOUR, 1, Mechanic.SELECT_ONE, "Same colour", "See a colour and tap the one of the same colour",
            (("language.matching.colour", P),), _plain(starter.same_colour), _picks(2, 3, 4),
        ),
        Template(
            Mode.SAME_SHAPE, 1, Mechanic.SELECT_ONE, "Same shape", "See a shape and tap the same shape",
            (("maths.geometry.same_shape", P),), _plain(starter.same_shape), _picks(2, 3, 4),
        ),
        Template(
            Mode.SAME_LETTER, 1, Mechanic.SELECT_ONE, "Same letter", "See a letter and tap the same letter",
            (("literacy.letters.same", P),), _plain(starter.same_letter), _picks(2, 3, 4),
        ),
        Template(
            Mode.SAME_NUMBER, 1, Mechanic.SELECT_ONE, "Same number", "See a number and tap the same number",
            (("maths.numerals.same", P),), starter.same_number, _numbers((2, 3), (3, 3), (3, 5), (4, 5)),
        ),
        Template(
            Mode.MATCHING, 1, Mechanic.SELECT_ONE, "Matching", "Find the animal, food or vehicle that was named",
            (("language.vocabulary.receptive", P),), _plain(choose.matching), _picks(2, 3, 4, 6, 8),
        ),
        Template(
            Mode.COLOURS, 1, Mechanic.SELECT_ONE, "Colours", "Find the shape of the named colour",
            (("language.vocabulary.colours", P),), _plain(choose.colours), _picks(2, 3, 4, 6, 8),
        ),
        Template(
            Mode.SHAPES, 1, Mechanic.SELECT_ONE, "Shapes", "Find the named coloured shape",
            (("maths.geometry.name_2d", P), ("language.vocabulary.colours", C)), _plain(choose.shapes),
            _picks(2, 3, 4, 6, 8),
        ),
        Template(
            Mode.LETTERS, 1, Mechanic.SELECT_ONE, "Letters", "Find the picture whose word starts with the letter",
            (("literacy.gpc.initial_letter", P), ("literacy.phonemic.initial_sound", S), ("language.vocabulary.receptive", C)),
            _plain(choose.letters), _picks(2, 3, 4, 6),
        ),
        Template(
            Mode.COUNTING, 1, Mechanic.SELECT_ONE, "Counting", "Count the pictures and tap the number",
            (("maths.counting.objects", P), ("maths.cardinality.last_number", S), ("maths.numerals.recognise", C)),
            choose.counting, _numbers((3, 3), (4, 5), (4, 8), (6, 10)),
        ),
        Template(
            Mode.MISSING, 1, Mechanic.FILL_MISSING, "Missing number", "Find the number missing from a run",
            (("maths.verbal_count.one_more", P), ("maths.verbal_count.forwards", S), ("maths.numerals.recognise", C)),
            choose.missing, _numbers((3, 5), (4, 10), (4, 20), (6, 20)),
        ),
        Template(
            Mode.QUICK_LOOK, 2, Mechanic.BRIEF_EXPOSURE, "Quick look", "See a few pictures for a moment and say how many",
            (("maths.subitising.perceptual", P), ("maths.numerals.recognise", C)), choose.quick_look,
            QUICK_LOOK_STEPS,
        ),
        Template(
            Mode.LISTEN, 1, Mechanic.AUDIO_RESPOND, "Listen", "Hear a word and tap the letter it starts with",
            (("literacy.gpc.grapheme_from_sound", P), ("literacy.phonemic.initial_sound", S)), _plain(choose.listen),
            _picks(2, 3, 4, 6),
        ),
        Template(
            Mode.GIVE, 1, Mechanic.GIVE_N, "Give a number", "Put the asked-for number of pictures in the basket",
            (("maths.cardinality.give_n", P), ("maths.counting.one_to_one", C)), place.give,
            (Level(3, "up to 3", 3), Level(5, "up to 5", 5), Level(6, "up to 8", 8), Level(8, "up to 10", 10)),
        ),
        Template(
            Mode.ORDER, 1, Mechanic.SEQUENCE, "Order", "Put numbers in order, smallest first",
            (("maths.comparison.order", P), ("maths.numerals.recognise", C)), place.order,
            (Level(3, "3 numbers to 5", 5), Level(4, "4 numbers to 10", 10), Level(5, "5 numbers to 10", 10), Level(5, "5 numbers to 20", 20)),
        ),
        Template(
            Mode.CAPITALS, 1, Mechanic.MATCH_PAIRS, "Capitals", "Put each small letter on its capital",
            (("literacy.letters.case_match", P), ("literacy.letters.identify", S)), _plain(place.capitals),
            tuple(Level(n, f"{n} pairs") for n in (2, 3, 4, 5)),
        ),
        Template(
            Mode.SORT_SOUNDS, 1, Mechanic.SORT, "Sort by sound", "Put pictures with the letter of their first sound",
            (("literacy.phonemic.initial_sound", P), ("literacy.gpc.sound_from_grapheme", S), ("language.vocabulary.receptive", C)),
            _plain(place.sort_sounds), tuple(Level(n, f"{n} pictures") for n in (4, 5, 6)),
        ),
        Template(
            Mode.SOUNDS, 1, Mechanic.AUDIO_RESPOND, "Sounds", "Hear a sound on its own and tap the letters that make it",
            (("literacy.gpc.grapheme_from_sound", P),), _plain(choose.sounds), _picks(2, 3, 4, 6),
        ),
        # Transfer kinds (0.13.0), one per skill a practice kind assesses: the same skill in another mechanic or
        # another representation, held out of practice (spec §9, §13; docs/content.md "Transfer kinds").
        Template(
            Mode.HEAR_FIND, 1, Mechanic.AUDIO_RESPOND, "Hear and find", "Hear a word, with no picture to match, and tap its picture",
            (("language.vocabulary.receptive", P),), _plain(choose.hear_find), _picks(2, 3, 4, 6), held_out=True,
        ),
        Template(
            Mode.COLOUR_BOX, 1, Mechanic.SORT, "Colour box", "Put every shape of the named colour in the box",
            (("language.vocabulary.colours", P),), _plain(place.colour_box),
            tuple(Level(n, f"{n} shapes") for n in (3, 4, 6)), held_out=True,
        ),
        Template(
            Mode.SHAPE_BOX, 1, Mechanic.SORT, "Shape box", "Put every shape of the named kind in the box, whatever its colour",
            (("maths.geometry.name_2d", P),), _plain(place.shape_box),
            tuple(Level(n, f"{n} shapes") for n in (3, 4, 6)), held_out=True,
        ),
        Template(
            Mode.WHICH_GROUP, 1, Mechanic.SELECT_ONE, "Which group", "Hear a number and tap the group with that many",
            (("maths.counting.objects", P), ("maths.cardinality.last_number", S)), choose.which_group,
            _numbers((2, 3), (3, 4), (4, 5)), held_out=True,
        ),
        Template(
            Mode.QUICK_DOTS, 2, Mechanic.BRIEF_EXPOSURE, "Quick dots", "See some dots for a moment and say how many",
            (("maths.subitising.perceptual", P), ("maths.numerals.recognise", C)), choose.quick_dots,
            QUICK_LOOK_STEPS, held_out=True,
        ),
        Template(
            Mode.ONE_MORE, 1, Mechanic.SELECT_ONE, "One more, one less", "Find the number one more or one less than another",
            (("maths.verbal_count.one_more", P), ("maths.numerals.recognise", C)), choose.one_more,
            _numbers((3, 5), (4, 10), (4, 20), (6, 20)), held_out=True,
        ),
        Template(
            Mode.BIGGEST, 1, Mechanic.SELECT_ONE, "Biggest number", "Tap the biggest or the smallest number",
            (("maths.comparison.order", P), ("maths.numerals.recognise", C)), choose.biggest,
            _numbers((3, 5), (4, 10), (4, 20), (6, 20)), held_out=True,
        ),
        Template(
            Mode.NUMBER_CARD, 1, Mechanic.GIVE_N, "Number card", "Put as many pictures in the basket as the card shows",
            (("maths.cardinality.give_n", P), ("maths.numerals.recognise", C), ("maths.counting.one_to_one", C)),
            place.number_card,
            (Level(3, "up to 3", 3), Level(5, "up to 5", 5), Level(6, "up to 8", 8), Level(8, "up to 10", 10)),
            held_out=True,
        ),
        Template(
            Mode.SMALL_LETTERS, 1, Mechanic.SELECT_ONE, "Small letters", "See a capital and tap its small letter",
            (("literacy.letters.case_match", P), ("literacy.letters.identify", S)), _plain(choose.small_letters),
            _picks(2, 3, 4, 6), held_out=True,
        ),
        Template(
            Mode.LETTER_BOX, 1, Mechanic.SORT, "Letter box", "Put every picture that starts with the letter in its box",
            (("literacy.gpc.initial_letter", P), ("literacy.phonemic.initial_sound", S), ("language.vocabulary.receptive", C)),
            _plain(place.letter_box), tuple(Level(n, f"{n} pictures") for n in (4, 5, 6)), held_out=True,
        ),
        Template(
            Mode.SAME_SOUND, 1, Mechanic.SELECT_ONE, "Same first sound", "Tap the picture that starts with the same sound",
            (("literacy.phonemic.initial_sound", P), ("language.vocabulary.receptive", C)), _plain(choose.same_sound),
            _picks(2, 3, 4), held_out=True,
        ),
        Template(
            Mode.FIRST_SOUNDS, 1, Mechanic.MATCH_PAIRS, "First sounds", "Put each picture on the letters of its first sound",
            (("literacy.gpc.grapheme_from_sound", P), ("literacy.phonemic.initial_sound", S), ("language.vocabulary.receptive", C)),
            _plain(place.first_sounds), tuple(Level(n, f"{n} pairs") for n in (2, 3, 4)), held_out=True,
        ),
        # The first steps' transfer kinds (0.14.0): the same matching by look, as pairs to put together.
        Template(
            Mode.PICTURE_TWINS, 2, Mechanic.MATCH_PAIRS, "Animal twins", "Put each animal on the same animal",
            (("language.matching.picture", P),), _plain(starter.picture_twins),
            tuple(Level(n, f"{n} pairs") for n in (2, 3)), held_out=True,
        ),
        Template(
            Mode.COLOUR_TWINS, 1, Mechanic.MATCH_PAIRS, "Colour twins", "Put each shape on the square of its colour",
            (("language.matching.colour", P),), _plain(starter.colour_twins),
            tuple(Level(n, f"{n} pairs") for n in (2, 3)), held_out=True,
        ),
        Template(
            Mode.SHAPE_TWINS, 1, Mechanic.MATCH_PAIRS, "Shape twins", "Put each shape on the same shape in another colour",
            (("maths.geometry.same_shape", P),), _plain(starter.shape_twins),
            tuple(Level(n, f"{n} pairs") for n in (2, 3)), held_out=True,
        ),
        Template(
            Mode.LETTER_TWINS, 1, Mechanic.MATCH_PAIRS, "Letter twins", "Put each letter on the same letter",
            (("literacy.letters.same", P),), _plain(starter.letter_twins),
            tuple(Level(n, f"{n} pairs") for n in (2, 3)), held_out=True,
        ),
        Template(
            Mode.NUMBER_TWINS, 1, Mechanic.MATCH_PAIRS, "Number twins", "Put each number on the same number",
            (("maths.numerals.same", P),), starter.number_twins,
            (Level(2, "2 pairs, numbers to 3", 3), Level(3, "3 pairs, numbers to 5", 5)), held_out=True,
        ),
    )
}  # fmt: skip

PLAYABLE = tuple(TEMPLATES)
PRACTICE = tuple(m for m, t in TEMPLATES.items() if not t.held_out)  # the kinds Mixed and Play's list offer
# Each transfer kind's skill, and each skill's transfer kind: one each (tests/unit/test_rounds.py checks every skill a
# practice kind assesses has one).
HELD_OUT: dict[Mode, str] = {
    m: next(s for s, r in t.skills if r is QRole.PRIMARY) for m, t in TEMPLATES.items() if t.held_out
}
TRANSFER: dict[str, Mode] = {s: m for m, s in HELD_OUT.items()}
# One picture per kind, for the tiles a learner picks between when offered a choice of two (engine/policy.py): what
# the round looks like, since a learner who cannot read yet picks by the picture and the spoken name.
PICTURES: dict[Mode, str] = {
    Mode.SAME_PICTURE: "\U0001f436",  # dog face
    Mode.SAME_COLOUR: "\U0001f534",  # red circle
    Mode.SAME_LETTER: "\U0001f170\ufe0f",  # A button
    Mode.SAME_NUMBER: "1\ufe0f\u20e3",  # keycap 1
    Mode.PICTURE_TWINS: "\U0001f46f",  # people with bunny ears: a pair
    Mode.SAME_SHAPE: "\U0001f7e5",  # red square
    Mode.COLOUR_TWINS: "\U0001f308",  # rainbow
    Mode.SHAPE_TWINS: "\U0001f536",  # orange diamond
    Mode.LETTER_TWINS: "\U0001f4dd",  # memo
    Mode.NUMBER_TWINS: "\U0001f3b2",  # die
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
    Mode.HEAR_FIND: "\U0001f5e3\ufe0f",  # speaking head
    Mode.COLOUR_BOX: "\U0001f58d\ufe0f",  # crayon
    Mode.SHAPE_BOX: "\U0001f537",  # blue diamond
    Mode.WHICH_GROUP: "\U0001f9ee",  # abacus
    Mode.QUICK_DOTS: "\U0001f535",  # blue circle
    Mode.ONE_MORE: "\u2795",  # plus
    Mode.BIGGEST: "\U0001f418",  # elephant
    Mode.NUMBER_CARD: "\U0001f0cf",  # card
    Mode.SMALL_LETTERS: "\U0001f521",  # abcd
    Mode.LETTER_BOX: "\U0001f4ee",  # postbox
    Mode.SAME_SOUND: "\U0001f3b5",  # music note
    Mode.FIRST_SOUNDS: "\U0001f9e9",  # puzzle piece
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
    level: int | None = None,
) -> Round:
    """One checked round. `seed` None picks one (returned in the round); the same mode, choices, seed, version, content
    and level give the same round, and the round's own (mode, version, choices, seed, content, level) rebuild it.
    `version` and `content` None are the current ones; any other is refused (only the current template and packs are
    kept). `level` None is a round with no step (the grown-up's choices, the kind's fixed range); a step must be one
    of the kind's and `choices` its step's (`at_level` makes such a round)."""
    if not MIN_CHOICES <= choices <= MAX_CHOICES:
        raise ValueError(f"choices must be between {MIN_CHOICES} and {MAX_CHOICES}, not {choices}")
    if level is not None and mode is Mode.MIXED:
        raise ValueError("a step of difficulty belongs to one kind of round, not to Mixed")
    if seed is None:
        seed = random.randrange(SEED_LIMIT)
    played = mode
    if mode is Mode.MIXED:
        # Mixed picks the kind and then the round's own seed from `seed`, so the round carries a (kind, seed) that
        # rebuilds it without going through Mixed. (0.2 drew the round from the same generator after picking the kind,
        # so a Mixed round's reported kind and seed rebuilt a different round.)
        pick = random.Random(seed)
        played = pick.choice(PRACTICE)  # never a transfer kind: those are held out (0.13.0; was every kind)
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
    top = None
    step: Level | None = None
    if level is not None:
        if not 0 <= level < len(t.levels):
            raise ValueError(f"{played} has steps 0 to {len(t.levels) - 1}, not {level}")
        if choices != t.levels[level].choices:
            raise ValueError(f"{played} step {level} lays out {t.levels[level].choices}, not {choices}")
        step = t.levels[level]
        top = step.top
    b = t.build(rng, choices, top)
    exposure_ms, peeks = b.exposure_ms, b.peeks
    if step is not None and step.exposure_ms is not None:  # a quick look's step sets its time and looks again
        exposure_ms, peeks = step.exposure_ms, step.peeks
    return check(
        Round(
            mode=played,
            version=t.version,
            content=now,
            choices=choices,
            seed=seed,
            level=level,
            mechanic=t.mechanic,
            skills=[SkillRole(skill=s, role=r) for s, r in t.skills],
            prompt=b.prompt,
            say=b.say or b.prompt,
            show=b.show,
            exposure_ms=exposure_ms,
            peeks=peeks,
            options=b.options,
            answer=b.answer,
            pieces=b.pieces,
            places=b.places,
            done_feedback=b.done_feedback,
        )
    )


def at_level(
    mode: Mode,
    level: int,
    seed: int | None = None,
    version: int | None = None,
    content: Mapping[str, int] | None = None,
) -> Round:
    """A round of `mode` at step `level`, with the step's number of choices."""
    if mode is Mode.MIXED:
        raise ValueError("a step of difficulty belongs to one kind of round, not to Mixed")
    t = TEMPLATES[mode]
    if not 0 <= level < len(t.levels):
        raise ValueError(f"{mode} has steps 0 to {len(t.levels) - 1}, not {level}")
    return generate(mode, t.levels[level].choices, seed, version, content, level)


def tries_allowed(tries: int, r: Round) -> int | None:
    """How many tries a round allows before it counts as missed: None for no limit (tries 0). A choose round counts
    taps, at most one fewer than its options so the last one is never a give-away; a place round counts checks."""
    if tries <= 0:
        return None
    if r.mechanic in PLACE:
        return tries
    return max(1, min(tries, len(r.options) - 1))
