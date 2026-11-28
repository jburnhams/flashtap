"""The first-steps kinds: the easiest rounds there are, where a new learner begins (packs/starter.toml).

Each one shows a thing and asks for the same thing again: an animal, a colour, a shape, a numeral to five, or (once
the first words are shown, 0.15.0) a letter. Nothing has to be named, counted or heard alone, so a learner with none
of the words yet can answer, and the prompt is spoken. The wrong options are always unlike the right one (a cow beside
a fish, never b beside d, numbers that are never each other's reversal), because these rounds are for showing the
learner what a round is, not for catching a mix-up.

- **Same picture** (shown as "Same animal" since 0.15.0: animals only, the owner asked for the very first rounds to
  be numbers to five, colours, shapes and animals), **Same colour**, **Same shape** (0.15.0), **Same letter**, **Same
  number** (`select_one`): the thing is shown big above two to four tiles. Same colour's right tile is the shown
  shape itself at two tiles, and from three tiles another shape of that colour where there is one (the red square for
  a red circle), so the step up asks for the colour and not the picture. Same shape does the same the other way: from
  three tiles its right tile is the shape in another colour, beside a wrong one in the shown colour, so the step up
  asks for the shape and not the colour. Same letter says the letter's name and sound in its prompt, on each tap
  and in the answer on a miss ("b, /b/"; version 2, 0.22.0), so the letter is heard as well as seen.
- **Picture twins** (animals), **Colour twins**, **Shape twins**, **Letter twins**, **Number twins**
  (`match_pairs`): the transfer kinds, held out of practice (rounds.TEMPLATES). Each piece goes onto the place that
  is the same: the same skill in another mechanic, which is what a transfer check asks (learners/transfer.py). Colour
  twins puts each circle or diamond on the square of its colour, so only the colour matches; Shape twins puts each
  shape on the same shape in another colour where there is one, so only the shape matches.
"""

import random
from collections.abc import Sequence

from flashtap import distractors as dx
from flashtap import lexicon
from flashtap.kinds import Body
from flashtap.kinds.choose import sound_token
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


def _animals() -> list[Thing]:
    """The animals, by id so a seed always sees the same order (0.15.0: before, every picture but the shapes)."""
    return sorted((t for t in lexicon.words().everything if t.category == "animals"), key=lambda t: t.id)


def _shapes() -> list[Thing]:
    return sorted(lexicon.words().shapes, key=lambda t: t.id)


def _letters() -> list[str]:
    return sorted({g.grapheme for g in lexicon.words().letters})


def _sound(letter: str) -> str:
    """The letter's sound: its first one-letter GPC in the inventory (each letter has one; c and k are both /k/)."""
    return next(g.phoneme for g in lexicon.words().letters if g.grapheme == letter)


def same_picture(rng: random.Random, choices: int) -> Body:
    animals = _animals()
    answer = rng.choice(animals)
    shown = [answer, *rng.sample([t for t in animals if t is not answer], choices - 1)]
    rng.shuffle(shown)
    return Body(
        prompt="Find the same one.",
        show=answer.picture,
        options=[_tile(t.id, t.picture, t.word, t is answer, "Yes! That's the same.", t.a) for t in shown],
        answer=answer.id,
    )


def same_colour(rng: random.Random, choices: int) -> Body:
    shapes = _shapes()
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


def same_shape(rng: random.Random, choices: int) -> Body:
    shapes = _shapes()
    # A shape with other shapes enough for the wrong tiles (a grown-up's eight leave out the square: five others)
    seen = rng.choice([t for t in shapes if sum(o.shape != t.shape for o in shapes) >= choices - 1])
    twins = [t for t in shapes if t.shape == seen.shape and t is not seen]
    answer = rng.choice(twins) if choices >= 3 and twins else seen
    others = [t for t in shapes if t.shape != seen.shape]
    rng.shuffle(others)
    # From three tiles one wrong tile wears the shown colour where one does, so the colour alone cannot find it
    others.sort(key=lambda t: not (choices >= 3 and t.colour == seen.colour))
    # Other shapes first, one of each, then any: the wrong tiles look as unlike each other as the shapes allow
    kinds: list[Thing] = []
    for t in others:
        if all(k.shape != t.shape for k in kinds):
            kinds.append(t)
    wrong = (kinds + [t for t in others if t not in kinds])[: choices - 1]
    shown = [answer, *wrong]
    rng.shuffle(shown)
    return Body(
        prompt="Find the same shape.",
        show=seen.picture,
        options=[_tile(t.id, t.picture, t.word, t is answer, "Yes! That's the same shape.", t.a) for t in shown],
        answer=answer.id,
    )


def same_letter(rng: random.Random, choices: int) -> Body:
    """Version 2 (0.22.0, the owner: "it should say the letter (both name and sound) in question and answer"): the
    prompt, each tap and the answer on a miss say the letter's name and then its sound ("b, /b/"). The letter is
    written alone and the voice reads it as its name, "a" too ("ay", not the article): espeak-ng, Kokoro's spelling
    to sound step, does so before a comma or a full stop. The sound is the letter's one GPC in the inventory."""
    chosen = _apart(rng, _letters(), choices)
    answer = chosen[0]
    rng.shuffle(chosen)
    said = {g: f"{g}, {sound_token(_sound(g))}" for g in chosen}
    return Body(
        prompt="Find the same letter.",
        say=f"Find the same letter: {said[answer]}.",
        show=answer,
        options=[
            Option(
                id=f"letter_{g}",
                picture=g,
                word=g,
                correct=g == answer,
                feedback=f"Yes! That's {said[g]}." if g == answer else f"No, that's {said[g]}.",
                distractor="" if g == answer else dx.RANDOM,
                reveal=f"The right one was {said[g]}." if g == answer else "",
            )
            for g in chosen
        ],
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
    chosen = rng.sample(_animals(), _pairs(choices))
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
    shapes = _shapes()
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


def shape_twins(rng: random.Random, choices: int) -> Body:
    shapes = _shapes()
    kinds = sorted({t.shape for t in shapes if t.shape})
    chosen = rng.sample(kinds, min(len(kinds), _pairs(choices)))  # three kinds of shape: three pairs at most
    pairs: list[tuple[Piece, Place]] = []
    for k in chosen:
        these = [t for t in shapes if t.shape == k]
        piece = rng.choice(these)
        # The same shape in another colour where there is one (the diamond has one colour, so it is its own twin)
        place = rng.choice([t for t in these if t is not piece] or these)
        pairs.append(
            (
                Piece(id=piece.id, picture=piece.picture, word=piece.word),
                Place(id=f"twin_{place.id}", picture=place.picture, word=place.word, takes=[piece.id], holds=1),
            )
        )
    return _twins(rng, pairs, "Put each shape on the same shape.", "Yes! Every shape is on its twin.")


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
