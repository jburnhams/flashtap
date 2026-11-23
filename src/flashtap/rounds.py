"""Rounds: one question, a set of pictures or numbers to tap, and exactly one right answer.

Ported from the TypeScript library's `services/gameService.ts`, with two changes the spec (docs/implementation-plan.md)
asks for before anything else is built on it:

- **Seeded.** A round is a pure function of (mode, choices, seed): the same three give the same round, so a round a
  child saw can be rebuilt exactly, and a test can walk thousands of seeds. The server picks a seed when the client
  sends none and returns it in the round.
- **Checked.** `check()` refuses a round with no right answer, more than one, repeated options or too few choices,
  and `generate()` runs it on every round. The old generators broke all of these somewhere: Colours could offer the red
  circle and the red square for "Which one is red?", Counting spun forever above ten choices (its distractors came from
  1-10), and every option printed its own name, so Letters and Colours were reading tasks.
"""

import random
from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, Field

from flashtap import lexicon
from flashtap.lexicon import Thing

MIN_CHOICES = 2
MAX_CHOICES = 8  # the smallest pool a mode draws from (Colours: the shapes not of one colour) still fills 8
SEED_LIMIT = 2**31  # seeds fit a JavaScript number and a 32-bit column


class Mode(StrEnum):
    MATCHING = "matching"
    COLOURS = "colours"
    SHAPES = "shapes"
    LETTERS = "letters"
    COUNTING = "counting"
    MIXED = "mixed"


# What each mode asks, for the mode list a person picks from.
MODE_NAMES: dict[Mode, tuple[str, str]] = {
    Mode.MATCHING: ("Matching", "Find the animal, food or vehicle that was named"),
    Mode.COLOURS: ("Colours", "Find the shape of the named colour"),
    Mode.SHAPES: ("Shapes", "Find the named coloured shape"),
    Mode.LETTERS: ("Letters", "Find the picture whose word starts with the letter"),
    Mode.COUNTING: ("Counting", "Count the pictures and tap the number"),
    Mode.MIXED: ("Mixed", "A different kind of round each time"),
}
# The skills each kind of round practises (ids in the content packs; tests/unit/test_content.py checks they exist). A
# round gives evidence on these once attempts are recorded (plan PR 4); the Content screen shows which skills have one.
MODE_SKILLS: dict[Mode, tuple[str, ...]] = {
    Mode.MATCHING: ("language.vocabulary.receptive",),
    Mode.COLOURS: ("language.vocabulary.colours",),
    Mode.SHAPES: ("maths.geometry.name_2d",),
    Mode.LETTERS: ("literacy.gpc.initial_letter",),
    Mode.COUNTING: ("maths.counting.objects", "maths.cardinality.last_number", "maths.numerals.recognise"),
}
PLAYABLE = (Mode.MATCHING, Mode.COLOURS, Mode.SHAPES, Mode.LETTERS, Mode.COUNTING)


class Option(BaseModel):
    id: str
    picture: str  # what the tile shows: an emoji or a numeral
    word: str  # what it is, for a screen reader; never printed on the tile, which would give the answer away
    correct: bool
    feedback: str  # said when this option is tapped: the success message on the right one


class Round(BaseModel):
    mode: Mode  # the mode actually played (never MIXED)
    seed: int = Field(ge=0, lt=SEED_LIMIT)
    prompt: str  # said aloud and shown: "Find the cow"
    show: str  # the big picture or word above the options: "🐄", "RED", "C", "🍎 🍎 🍎"
    options: list[Option]
    answer: str  # the right option's id
    tries: int | None = (
        None  # taps allowed before the round counts as missed; None: no limit. Set by the server from the settings
    )


class InvalidRound(ValueError):
    """A generated round that breaks a rule `check` enforces: a bug in a generator, never a child's mistake."""


def check(r: Round) -> Round:
    ids = [o.id for o in r.options]
    right = [o for o in r.options if o.correct]
    if len(right) != 1:
        raise InvalidRound(f"{r.mode} seed {r.seed}: {len(right)} right answers")
    if right[0].id != r.answer:
        raise InvalidRound(f"{r.mode} seed {r.seed}: answer {r.answer} is not the right option {right[0].id}")
    if len(set(ids)) != len(ids) or len({o.picture for o in r.options}) != len(ids):
        raise InvalidRound(f"{r.mode} seed {r.seed}: repeated options")
    if len(ids) < MIN_CHOICES:
        raise InvalidRound(f"{r.mode} seed {r.seed}: only {len(ids)} options")
    return r


def _pick(rng: random.Random, pool: Sequence[Thing], answer: Thing, choices: int) -> list[Thing]:
    """The answer and `choices - 1` others from `pool`, shuffled. Callers pass a pool that holds no second right answer."""
    others = [t for t in pool if t.id != answer.id]
    shown = [answer, *rng.sample(others, min(choices - 1, len(others)))]
    rng.shuffle(shown)
    return shown


def _options(shown: list[Thing], answer: Thing, success: str) -> list[Option]:
    return [
        Option(
            id=t.id,
            picture=t.picture,
            word=t.word,
            correct=t is answer,
            feedback=success if t is answer else f"No, that's {t.a}.",
        )
        for t in shown
    ]


def _matching(rng: random.Random, choices: int, seed: int) -> Round:
    pool = rng.choice(lexicon.MATCHING_POOLS)  # one category per round: a cow among buses is too easy
    answer = rng.choice(pool)
    shown = _pick(rng, pool, answer, choices)
    return Round(
        mode=Mode.MATCHING,
        seed=seed,
        prompt=f"Find the {answer.word}.",
        show=answer.picture,
        options=_options(shown, answer, f"Yes! You found the {answer.word}."),
        answer=answer.id,
    )


def _colours(rng: random.Random, choices: int, seed: int) -> Round:
    answer = rng.choice(lexicon.SHAPES)
    colour = answer.colour or ""
    pool = [t for t in lexicon.SHAPES if t.colour != colour or t is answer]  # exactly one shape of that colour
    shown = _pick(rng, pool, answer, choices)
    return Round(
        mode=Mode.COLOURS,
        seed=seed,
        prompt=f"Which one is {colour}?",
        show=colour.upper(),
        options=_options(shown, answer, f"Yes! That one is {colour}."),
        answer=answer.id,
    )


def _shapes(rng: random.Random, choices: int, seed: int) -> Round:
    answer = rng.choice(lexicon.SHAPES)
    shown = _pick(rng, lexicon.SHAPES, answer, choices)
    return Round(
        mode=Mode.SHAPES,
        seed=seed,
        prompt=f"Find the {answer.word}.",
        show=answer.picture,
        options=_options(shown, answer, f"Yes! You found the {answer.word}."),
        answer=answer.id,
    )


def _letters(rng: random.Random, choices: int, seed: int) -> Round:
    answer = rng.choice(lexicon.LETTER_WORDS)
    letter = answer.letter or ""
    pool = [t for t in lexicon.LETTER_WORDS if t.letter != letter or t is answer]  # only one word with that letter
    shown = _pick(rng, pool, answer, choices)
    return Round(
        mode=Mode.LETTERS,
        seed=seed,
        prompt=f"What starts with the letter {letter}?",
        show=letter,
        options=_options(shown, answer, f"Yes! {answer.label} starts with {letter}."),
        answer=answer.id,
    )


COUNT_MOST = 5  # up to five pictures in the row: enough to count, few enough to see at once
NUMBERS = range(1, 11)


def _counting(rng: random.Random, choices: int, seed: int) -> Round:
    thing = rng.choice(lexicon.COUNTABLE)
    n = rng.randint(1, COUNT_MOST)
    others = rng.sample([k for k in NUMBERS if k != n], choices - 1)  # 9 others, and MAX_CHOICES is 8
    shown = [n, *others]
    rng.shuffle(shown)
    many = thing.word if n == 1 else thing.many
    return Round(
        mode=Mode.COUNTING,
        seed=seed,
        prompt=f"How many {thing.many} are there?",
        show=" ".join([thing.picture] * n),
        options=[
            Option(
                id=f"n{k}",
                picture=str(k),
                word=str(k),
                correct=k == n,
                feedback=f"Yes! There {'is' if n == 1 else 'are'} {n} {many}." if k == n else f"No, that's {k}.",
            )
            for k in shown
        ],
        answer=f"n{n}",
    )


_GENERATORS = {
    Mode.MATCHING: _matching,
    Mode.COLOURS: _colours,
    Mode.SHAPES: _shapes,
    Mode.LETTERS: _letters,
    Mode.COUNTING: _counting,
}


def generate(mode: Mode, choices: int, seed: int | None = None) -> Round:
    """One checked round. `seed` None picks one (returned in the round); the same mode, choices and seed give the same round."""
    if not MIN_CHOICES <= choices <= MAX_CHOICES:
        raise ValueError(f"choices must be between {MIN_CHOICES} and {MAX_CHOICES}, not {choices}")
    if seed is None:
        seed = random.randrange(SEED_LIMIT)
    rng = random.Random(seed)
    played = rng.choice(PLAYABLE) if mode is Mode.MIXED else mode
    return check(_GENERATORS[played](rng, choices, seed))


def tries_allowed(tries: int, options: int) -> int | None:
    """How many taps a round allows before it counts as missed: None for no limit (tries 0), else `tries`, at most one fewer than the options so the last one is never a give-away."""
    return None if tries <= 0 else max(1, min(tries, options - 1))
