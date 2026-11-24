"""The kinds answered by an arrangement: pieces put into places, checked when the learner says they are done.

How the answer is written (`Place.takes` and `holds`) is in `flashtap.mechanics`. `choices` is how many pieces (or
pairs) the round lays out, clamped to what each kind can use; Give and Order also take `top`, the largest number of a
step of difficulty (`rounds.Level`; None keeps the fixed range they had before steps):

- **Give** (`give_n`): "Put 4 apples in the basket", from a pile with more than 4. The basket takes every apple and
  holds 4, so any 4 are right and 5 is not: stopping at the number is the skill (`maths.cardinality.give_n`).
- **Order** (`sequence`): three to five different numerals into first, second... places, smallest first.
- **Capitals** (`match_pairs`): each small letter onto its capital. The letters are chosen so that look-alikes (b and
  d, m and w) meet in one round when they can, since telling them apart is what is being practised.
- **Sort by sound** (`sort`): pictures into two groups by their first sound, each group a letter. The two letters
  always stand for different sounds (never c and k), so every picture has one place.
"""

import random

from flashtap import distractors as dx
from flashtap import lexicon
from flashtap.kinds import Body
from flashtap.mechanics import InvalidRound, Piece, Place

GIVE_MOST = 5  # the asked-for number: up to five, the range `maths.cardinality.give_n` starts with
PILE_MOST = 10


def give(rng: random.Random, choices: int, top: int | None = None) -> Body:
    """`top` is the most that may be asked for (`GIVE_MOST` without a step); the pile grows to two more than that."""
    most = GIVE_MOST if top is None else top
    thing = rng.choice(lexicon.words().countable)
    n = rng.randint(1, most)
    pile = min(
        max(PILE_MOST, most + 2), max(n + 2, choices + 1)
    )  # always more than asked for, so "all of them" is never the answer
    pieces = [Piece(id=f"{thing.id}{i + 1}", picture=thing.picture, word=thing.word) for i in range(pile)]
    many = thing.word if n == 1 else thing.many
    return Body(
        prompt=f"Put {n} {many} in the basket.",
        pieces=pieces,
        places=[Place(id="basket", picture="🧺", word="the basket", takes=[p.id for p in pieces], holds=n)],
        done_feedback=f"Yes! There {'is' if n == 1 else 'are'} {n} {many} in the basket.",
    )


ORDINALS = ("first", "second", "third", "fourth", "fifth")
ORDER_RANGE = (0, 10)


def order(rng: random.Random, choices: int, top: int | None = None) -> Body:
    low, high = ORDER_RANGE if top is None else (0, top)
    k = max(3, min(len(ORDINALS), choices))
    numbers = sorted(rng.sample(range(low, high + 1), k))
    pieces = [Piece(id=f"n{n}", picture=str(n), word=str(n)) for n in numbers]
    rng.shuffle(pieces)
    return Body(
        prompt="Put the numbers in order, smallest first.",
        pieces=pieces,
        places=[
            Place(id=w, picture="", word=w, takes=[f"n{n}"], holds=1) for w, n in zip(ORDINALS, numbers, strict=False)
        ],
        done_feedback=f"Yes! {', '.join(map(str, numbers[:-1]))} and {numbers[-1]}.",
    )


PAIRS = (2, 5)


def capitals(rng: random.Random, choices: int) -> Body:
    k = max(PAIRS[0], min(PAIRS[1], choices))
    alphabet = sorted({g.grapheme for g in lexicon.words().letters})
    first = rng.choice(alphabet)
    look = [(g, dx.CONFUSABLE_GRAPHEME) for g in dx.confusable_graphemes(first) if g in alphabet]
    chosen = [first, *(g for g, _ in dx.fill(rng, k - 1, look, alphabet, {first}))]
    rng.shuffle(chosen)
    pieces = [Piece(id=f"small_{g}", picture=g, word=f"small {g}") for g in chosen]
    rng.shuffle(pieces)
    return Body(
        prompt="Put each small letter on its capital.",
        pieces=pieces,
        places=[
            Place(id=f"capital_{g}", picture=g.upper(), word=f"capital {g.upper()}", takes=[f"small_{g}"], holds=1)
            for g in chosen
        ],
        done_feedback="Yes! Every letter is with its capital.",
    )


SORT_PIECES = (4, 6)  # two groups of two or three


def sort_sounds(rng: random.Random, choices: int) -> Body:
    words = lexicon.words()
    total = max(SORT_PIECES[0], min(SORT_PIECES[1], choices))
    by_sound: dict[str, list[lexicon.Thing]] = {}
    for t in words.sound_words:
        if t.onset:
            by_sound.setdefault(t.onset.phoneme, []).append(t)
    # Group by sound, then show each group as the letter its pictures share: a sound spelt two ways (c and k) has
    # words under both, so keep only the sounds whose pictures all start with one letter.
    groups = {
        p: ts
        for p, ts in by_sound.items()
        if len(ts) >= total // 2 + total % 2 and len({t.onset.grapheme for t in ts if t.onset}) == 1
    }
    a, b = rng.sample(sorted(groups), 2)
    sizes = (total - total // 2, total // 2)
    sides = [(p, rng.sample(groups[p], n)) for p, n in zip((a, b), sizes, strict=True)]
    pieces = [Piece(id=t.id, picture=t.picture, word=t.word) for _, ts in sides for t in ts]
    rng.shuffle(pieces)
    places: list[Place] = []
    for _, ts in sides:
        onset = ts[0].onset
        if onset is None:  # sound_words all have a one-letter onset
            raise InvalidRound(f"sort_sounds: {ts[0].id} has no first sound")
        letter = onset.grapheme
        places.append(Place(id=f"sound_{letter}", picture=letter, word=letter, takes=[t.id for t in ts], holds=len(ts)))
    return Body(
        prompt="Put each picture with the letter it starts with.",
        say="Put each picture with the letter it starts with. Say the word, and listen for its first sound.",
        pieces=pieces,
        places=places,
        done_feedback="Yes! Every picture is with its first sound.",
    )
