"""The first-steps kinds (0.14.0): the easiest rounds there are, where a new learner begins (packs/starter.toml).

Each one shows a thing and asks for the same thing again: a picture, a colour, a letter or a numeral. Nothing has to
be named, counted or heard alone, so a learner with none of the words yet can answer, and the prompt is spoken. The
wrong options are always unlike the right one (a cow beside a bus, never b beside d, numbers that are never each
other's reversal), because these rounds are for showing the learner what a round is, not for catching a mix-up.

- **Same picture**, **Same colour**, **Same letter**, **Same number** (`select_one`): the thing is shown big above
  two to four tiles. Same colour's right tile is the shown shape itself at two tiles, and from three tiles another
  shape of that colour where there is one (the red square for a red circle), so the step up asks for the colour and
  not the picture.
- **Picture twins**, **Colour twins**, **Letter twins**, **Number twins** (`match_pairs`): the transfer kinds, held
  out of practice (rounds.TEMPLATES). Each piece goes onto the place that is the same: the same skill in another
  mechanic, which is what a transfer check asks (learners/transfer.py). Colour twins puts each circle or diamond on
  the square of its colour, so only the colour matches.
"""

import random
from collections.abc import Sequence

from flashtap import distractors as dx
from flashtap import lexicon
from flashtap.kinds import Body
from flashtap.lexicon import Thing
from flashtap.mechanics import Option, Piece, Place

NUMBERS_TOP = 3  # the numerals in play when a step names none: one to three
TWINS = (2, 4)  # pairs a twins round lays out: four kinds of thing, four colours with a square and another shape


def _tile(id: str, picture: str, word: str, right: bool, said: str, called: str = "") -> Option:
    """One tile; `called` is how the wrong-tap feedback names it ("a cow"), the word itself when empty."""
    return Option(
        id=id,
        picture=picture,
        word=word,
        correct=right,
        feedback=said if right else f"No, that's {called or word}.",
        distractor="" if right else dx.RANDOM,
    )


def _pairs(choices: int) -> int:
    return max(TWINS[0], min(TWINS[1], choices))


def _apart(rng: random.Random, pool: Sequence[str], k: int) -> list[str]:
    """`k` letters from `pool`, no two of them look-alikes (b d p q, m w, n u): the first is the answer."""
    shuffled = list(pool)
    rng.shuffle(shuffled)
    chosen: list[str] = []
    for g in shuffled:
        if len(chosen) == k:
            break
        if all(g not in dx.confusable_graphemes(c) for c in chosen):
            chosen.append(g)
    return chosen


def _things() -> list[Thing]:
    """Every picture but the shapes, by id so a seed always sees the same order."""
    return sorted((t for t in lexicon.words().everything if t.category != "shapes"), key=lambda t: t.id)


def _letters() -> list[str]:
    return sorted({g.grapheme for g in lexicon.words().letters})


def same_picture(rng: random.Random, choices: int) -> Body:
    things = _things()
    answer = rng.choice(things)
    # From other kinds of thing only: a cow among a bus and an apple, never among other animals.
    others = [t for t in things if t.category != answer.category]
    shown = [answer, *rng.sample(others, choices - 1)]
    rng.shuffle(shown)
    return Body(
        prompt="Find the same one.",
        show=answer.picture,
        options=[_tile(t.id, t.picture, t.word, t is answer, "Yes! That's the same.", t.a) for t in shown],
        answer=answer.id,
    )


def same_colour(rng: random.Random, choices: int) -> Body:
    shapes = sorted(lexicon.words().shapes, key=lambda t: t.id)
    seen = rng.choice(shapes)
    twins = [t for t in shapes if t.colour == seen.colour and t is not seen]
    answer = rng.choice(twins) if choices >= 3 and twins else seen
    by_colour: dict[str, list[Thing]] = {}
    for t in shapes:
        if t.colour and t.colour != seen.colour:
            by_colour.setdefault(t.colour, []).append(t)
    # Every wrong tile a colour of its own while there are colours enough (seven: up to six wrong); a grown-up's
    # eight tiles repeat a wrong colour in another shape, which is still not the shown colour.
    firsts = [rng.choice(by_colour[c]) for c in rng.sample(sorted(by_colour), min(choices - 1, len(by_colour)))]
    rest = [t for ts in by_colour.values() for t in ts if t not in firsts]
    wrong = firsts + rng.sample(rest, choices - 1 - len(firsts))
    shown = [answer, *wrong]
    rng.shuffle(shown)
    return Body(
        prompt="Find the same colour.",
        show=seen.picture,
        options=[_tile(t.id, t.picture, t.word, t is answer, "Yes! That's the same colour.", t.a) for t in shown],
        answer=answer.id,
    )


def same_letter(rng: random.Random, choices: int) -> Body:
    chosen = _apart(rng, _letters(), choices)
    answer = chosen[0]
    rng.shuffle(chosen)
    return Body(
        prompt="Find the same letter.",
        show=answer,
        options=[_tile(f"letter_{g}", g, g, g == answer, "Yes! That's the same letter.") for g in chosen],
        answer=f"letter_{answer}",
    )


def same_number(rng: random.Random, choices: int, top: int | None = None) -> Body:
    # one to `top` (at most five: no 6 and 9 to mix up); a round played by hand has numbers enough for its tiles
    chosen = rng.sample(range(1, (top or max(NUMBERS_TOP, choices)) + 1), choices)
    answer = chosen[0]
    rng.shuffle(chosen)
    return Body(
        prompt="Find the same number.",
        show=str(answer),
        options=[_tile(f"n{k}", str(k), str(k), k == answer, "Yes! That's the same number.") for k in chosen],
        answer=f"n{answer}",
    )


def _twins(rng: random.Random, pairs: list[tuple[Piece, Place]], prompt: str, done: str) -> Body:
    pieces = [p for p, _ in pairs]
    places = [s for _, s in pairs]
    rng.shuffle(pieces)
    rng.shuffle(places)
    return Body(prompt=prompt, pieces=pieces, places=places, done_feedback=done)


def picture_twins(rng: random.Random, choices: int) -> Body:
    choices = _pairs(choices)
    things = _things()
    chosen: list[Thing] = []
    for t in rng.sample(things, len(things)):  # one of each kind of thing, so no two pictures are alike
        if len(chosen) == choices:
            break
        if all(c.category != t.category for c in chosen):
            chosen.append(t)
    return _twins(
        rng,
        [
            (
                Piece(id=t.id, picture=t.picture, word=t.word),
                Place(id=f"twin_{t.id}", picture=t.picture, word=t.word, takes=[t.id], holds=1),
            )
            for t in chosen
        ],
        "Put each picture on the same picture.",
        "Yes! Every picture is on its twin.",
    )


def colour_twins(rng: random.Random, choices: int) -> Body:
    shapes = sorted(lexicon.words().shapes, key=lambda t: t.id)
    squares = {t.colour: t for t in shapes if t.shape == "square" and t.colour}
    others = {t.colour: t for t in shapes if t.shape != "square" and t.colour in squares}  # a circle or a diamond
    colours = rng.sample(sorted(others), _pairs(choices))
    return _twins(
        rng,
        [
            (
                Piece(id=others[c].id, picture=others[c].picture, word=others[c].word),
                Place(
                    id=squares[c].id, picture=squares[c].picture, word=squares[c].word, takes=[others[c].id], holds=1
                ),
            )
            for c in colours
        ],
        "Put each shape on the square of the same colour.",
        "Yes! Every shape is on its colour.",
    )


def letter_twins(rng: random.Random, choices: int) -> Body:
    chosen = _apart(rng, _letters(), _pairs(choices))
    return _twins(
        rng,
        [
            (
                Piece(id=f"letter_{g}", picture=g, word=g),
                Place(id=f"twin_{g}", picture=g, word=g, takes=[f"letter_{g}"], holds=1),
            )
            for g in chosen
        ],
        "Put each letter on the same letter.",
        "Yes! Every letter is on its twin.",
    )


def number_twins(rng: random.Random, choices: int, top: int | None = None) -> Body:
    k = _pairs(choices)
    chosen = rng.sample(range(1, (top or max(NUMBERS_TOP, k)) + 1), k)
    return _twins(
        rng,
        [
            (
                Piece(id=f"n{k}", picture=str(k), word=str(k)),
                Place(id=f"twin_{k}", picture=str(k), word=str(k), takes=[f"n{k}"], holds=1),
            )
            for k in chosen
        ],
        "Put each number on the same number.",
        "Yes! Every number is on its twin.",
    )
