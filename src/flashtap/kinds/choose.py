"""The one-tap kinds: a question, two to eight options, exactly one right.

The number kinds (Counting, Quick look, Missing) also take `top`, the largest number a step of difficulty asks about
(`rounds.Level`); None keeps the fixed ranges they had before steps, so older rounds rebuild unchanged.

The first five are the original rounds (ported from the TypeScript library in 0.2.0), now with their wrong options
chosen by named generators (`flashtap.distractors`). The last three are new with the mechanics (plan PR 3):

- **Missing** (`fill_missing`): a run of numbers with one gap. The gap's neighbours are offered too, because saying
  the number before or after is the common slip.
- **Quick look** (`brief_exposure`): up to five pictures shown for a moment, then hidden. Long enough to see, too
  short to count one by one, so a right answer is evidence of subitising rather than counting.
- **Listen** (`audio_respond`): a word is said (and its picture shown, never its spelling) and the learner taps the
  letter it starts with. A letter that spells the same sound (c and k for /k/) is never offered: it would also be
  right. Wrong letters are the right one's look-alikes (b d p q) and its sound's neighbours (/p/ for /b/) first.
- **Sounds** (`audio_respond`): one sound of the phonics inventory is said on its own (/ʃ/, never a word that holds
  it), and the learner taps the letters that write it (sh). Unlike Listen it asks nothing of hearing a word's first
  sound, so it is evidence of the correspondence alone. A grapheme that also writes the sound (c, k and ck for /k/) is
  never offered. The sound is `/IPA/` inside `say`, which the voice clips play from a recording (`flashtap.voice`);
  no browser voice can say /ʃ/ alone.
"""

import math
import random

from flashtap import distractors as dx
from flashtap import lexicon
from flashtap.kinds import Body
from flashtap.lexicon import Thing
from flashtap.mechanics import InvalidRound, Option


def _pick(
    rng: random.Random, pool: tuple[Thing, ...], answer: Thing, choices: int, why: str
) -> list[tuple[Thing, str]]:
    """The answer and `choices - 1` others from `pool`, shuffled; the others are named `why`. Callers pass a pool that
    holds no second right answer."""
    others = [t for t in pool if t.id != answer.id]
    shown = [(answer, ""), *((t, why) for t in rng.sample(others, min(choices - 1, len(others))))]
    rng.shuffle(shown)
    return shown


def _options(shown: list[tuple[Thing, str]], answer: Thing, success: str) -> list[Option]:
    return [
        Option(
            id=t.id,
            picture=t.picture,
            word=t.word,
            correct=t is answer,
            feedback=success if t is answer else f"No, that's {t.a}.",
            distractor="" if t is answer else why,
        )
        for t, why in shown
    ]


def matching(rng: random.Random, choices: int) -> Body:
    pool = rng.choice(lexicon.words().matching_pools)  # one category per round: a cow among buses is too easy
    answer = rng.choice(pool)
    shown = _pick(rng, pool, answer, choices, dx.SAME_CATEGORY)
    return Body(
        prompt=f"Find the {answer.word}.",
        show=answer.picture,
        options=_options(shown, answer, f"Yes! You found the {answer.word}."),
        answer=answer.id,
    )


def colours(rng: random.Random, choices: int) -> Body:
    shapes = lexicon.words().shapes
    answer = rng.choice(shapes)
    colour = answer.colour or ""
    pool = tuple(t for t in shapes if t.colour != colour or t is answer)  # exactly one shape of that colour
    shown = _pick(rng, pool, answer, choices, dx.SAME_CATEGORY)
    return Body(
        prompt=f"Which one is {colour}?",
        show=colour.upper(),
        options=_options(shown, answer, f"Yes! That one is {colour}."),
        answer=answer.id,
    )


def shapes(rng: random.Random, choices: int) -> Body:
    pool = lexicon.words().shapes
    answer = rng.choice(pool)
    shown = _pick(rng, pool, answer, choices, dx.SAME_CATEGORY)
    return Body(
        prompt=f"Find the {answer.word}.",
        show=answer.picture,
        options=_options(shown, answer, f"Yes! You found the {answer.word}."),
        answer=answer.id,
    )


def letters(rng: random.Random, choices: int) -> Body:
    """ "What starts with D?": the pictures whose letters look like D's small letter (b, p, q) or whose sounds are
    D's neighbours (/t/, /n/) come first among the wrong ones."""
    words = lexicon.words()
    answer = rng.choice(words.letter_words)
    letter = answer.letter or ""
    phoneme = answer.onset.phoneme if answer.onset else ""
    others = [t for t in words.letter_words if t.onset and t.onset.phoneme != phoneme]  # never a second right word
    rng.shuffle(others)
    look = set(dx.confusable_graphemes(letter.lower()))
    near = set(dx.phonological_neighbours(phoneme))
    preferred = [(t, dx.CONFUSABLE_GRAPHEME) for t in others if t.onset and t.onset.grapheme in look]
    preferred += [(t, dx.PHONOLOGICAL_NEIGHBOUR) for t in others if t.onset and t.onset.phoneme in near]
    # Half the wrong pictures at most come from the near ones, so the round is not all hard.
    wanted = choices - 1
    shown = dx.fill(rng, math.ceil(wanted / 2), preferred, [], {answer})
    shown += dx.fill(rng, wanted - len(shown), [], others, {answer, *(t for t, _ in shown)})
    both = [(answer, ""), *shown]
    rng.shuffle(both)
    return Body(
        prompt=f"What starts with the letter {letter}?",
        show=letter,
        options=_options(both, answer, f"Yes! {answer.label} starts with {letter}."),
        answer=answer.id,
    )


def _numerals(
    rng: random.Random, n: int, low: int, high: int, choices: int, near_share: float
) -> list[tuple[int, str]]:
    """n and `choices - 1` wrong numerals from [low, high], shuffled: n's reversal (6 for 9) when in range, then up to
    `near_share` of the wrong ones from the nearest numbers, the rest at random."""
    wanted = choices - 1
    flip = dx.reversal(n)
    preferred = [(flip, dx.REVERSAL)] if flip is not None and low <= flip <= high else []
    preferred += [(k, dx.NEAR_NUMBER) for k in dx.near_numbers(n, low, high, rng)]
    wrong = dx.fill(rng, max(1, math.ceil(wanted * near_share)), preferred, [], {n})
    wrong += dx.fill(rng, wanted - len(wrong), [], list(range(low, high + 1)), {n, *(k for k, _ in wrong)})
    shown = [(n, ""), *wrong]
    rng.shuffle(shown)
    return shown


def _number_options(shown: list[tuple[int, str]], n: int, success: str) -> list[Option]:
    return [
        Option(
            id=f"n{k}",
            picture=str(k),
            word=str(k),
            correct=k == n,
            feedback=success if k == n else f"No, that's {k}.",
            distractor=why,
        )
        for k, why in shown
    ]


COUNT_MOST = 5  # up to five pictures in the row: enough to count, few enough to see at once
NUMBERS = (1, 10)  # the numerals Counting and Quick look offer
SMALL_NUMBERS = (1, 5)  # the numerals offered when the count is at most 4 (an easier step): no 9 to tap for a 3


def _counted(top: int | None) -> tuple[int, tuple[int, int]]:
    """The most pictures shown and the numerals offered: the 0.4 constants without a step (`top` None, so a round
    made before steps rebuilds exactly), else up to `top` pictures, among numerals to 5 or to 10."""
    if top is None:
        return COUNT_MOST, NUMBERS
    return top, (SMALL_NUMBERS if top < SMALL_NUMBERS[1] else NUMBERS)


def counting(rng: random.Random, choices: int, top: int | None = None) -> Body:
    most, numerals = _counted(top)
    thing = rng.choice(lexicon.words().countable)
    n = rng.randint(1, most)
    many = thing.word if n == 1 else thing.many
    return Body(
        prompt=f"How many {thing.many} are there?",
        show=" ".join([thing.picture] * n),
        options=_number_options(
            _numerals(rng, n, *numerals, choices, 0.5), n, f"Yes! There {'is' if n == 1 else 'are'} {n} {many}."
        ),
        answer=f"n{n}",
    )


QUICK_LOOK_MS = 1500  # long enough to see up to five, too short to point and count them one by one


def quick_look(rng: random.Random, choices: int, top: int | None = None) -> Body:
    most, numerals = _counted(top)
    thing = rng.choice(lexicon.words().countable)
    n = rng.randint(1, most)
    many = thing.word if n == 1 else thing.many
    return Body(
        prompt="How many did you see?",
        say=f"Look quickly! How many {thing.many}?",
        show=" ".join([thing.picture] * n),
        exposure_ms=QUICK_LOOK_MS,
        options=_number_options(
            _numerals(rng, n, *numerals, choices, 0.5), n, f"Yes! There {'was' if n == 1 else 'were'} {n} {many}."
        ),
        answer=f"n{n}",
    )


MISSING_RANGE = (0, 10)  # numerals 0 to 10: the first pack's slice (maths.numerals.zero is in it)
RUN = 5  # numbers shown in a run, the gap included


def missing(rng: random.Random, choices: int, top: int | None = None) -> Body:
    low, high = MISSING_RANGE if top is None else (0, top)
    start = rng.randint(low, high - RUN + 1)
    run = list(range(start, start + RUN))
    gap = rng.randrange(RUN)
    n = run[gap]
    shown = " ".join("?" if i == gap else str(k) for i, k in enumerate(run))
    return Body(
        prompt="Which number is missing?",
        show=shown,
        options=_number_options(_numerals(rng, n, low, high, choices, 0.5), n, f"Yes! {n} is missing."),
        answer=f"n{n}",
    )


def listen(rng: random.Random, choices: int) -> Body:
    words = lexicon.words()
    answer = rng.choice(words.sound_words)
    onset = answer.onset
    if onset is None:  # sound_words all have a one-letter onset
        raise InvalidRound(f"listen: {answer.id} has no first sound")
    letter = onset.grapheme
    same_sound = {g.grapheme for g in words.letters if g.phoneme == onset.phoneme}  # c and k for /k/: both right
    by_sound: dict[str, list[str]] = {}
    for g in words.letters:
        by_sound.setdefault(g.phoneme, []).append(g.grapheme)
    preferred = [
        (g, dx.CONFUSABLE_GRAPHEME) for g in dx.confusable_graphemes(letter) if g in {x.grapheme for x in words.letters}
    ]
    preferred += [
        (g, dx.PHONOLOGICAL_NEIGHBOUR) for p in dx.phonological_neighbours(onset.phoneme) for g in by_sound.get(p, [])
    ]
    wanted = choices - 1
    wrong = dx.fill(rng, math.ceil(wanted / 2), preferred, [], same_sound)
    wrong += dx.fill(
        rng, wanted - len(wrong), [], [g.grapheme for g in words.letters], same_sound | {g for g, _ in wrong}
    )
    shown = [(letter, ""), *wrong]
    rng.shuffle(shown)
    return Body(
        prompt="Listen, then tap the letter it starts with.",
        say=f"{answer.word}. Which letter does {answer.word} start with?",
        show=answer.picture,
        options=[
            Option(
                id=f"l_{g}",
                picture=g,
                word=g,
                correct=g == letter,
                feedback=f"Yes! {answer.label} starts with {letter}." if g == letter else f"No, that's {g}.",
                distractor=why,
            )
            for g, why in shown
        ],
        answer=f"l_{letter}",
    )


def sound_token(phoneme: str) -> str:
    """How a sound on its own is written inside `say`: /ʃ/. `flashtap.voice` splits it out and plays its recording."""
    return f"/{phoneme}/"


def sounds(rng: random.Random, choices: int) -> Body:
    gpcs = lexicon.words().gpcs
    answer = rng.choice(gpcs)
    graphemes = sorted({g.grapheme for g in gpcs})
    same_sound = {g.grapheme for g in gpcs if g.phoneme == answer.phoneme}  # c, k, ck for /k/: each would be right
    by_sound: dict[str, list[str]] = {}
    for g in gpcs:
        by_sound.setdefault(g.phoneme, []).append(g.grapheme)
    preferred = [(g, dx.CONFUSABLE_GRAPHEME) for g in dx.confusable_graphemes(answer.grapheme) if g in graphemes]
    preferred += [
        (g, dx.PHONOLOGICAL_NEIGHBOUR) for p in dx.phonological_neighbours(answer.phoneme) for g in by_sound.get(p, [])
    ]
    wanted = choices - 1
    wrong = dx.fill(rng, math.ceil(wanted / 2), preferred, [], same_sound)
    wrong += dx.fill(rng, wanted - len(wrong), [], graphemes, same_sound | {g for g, _ in wrong})
    letters = answer.grapheme
    shown = [(letters, ""), *wrong]
    rng.shuffle(shown)
    return Body(
        prompt="Listen, then tap the letters that make the sound.",
        say=f"Listen. {sound_token(answer.phoneme)} Which letters make that sound?",
        show="\U0001f50a",  # speaker: the sound is heard, never printed
        options=[
            Option(
                id=f"g_{g}",
                picture=g,
                word=g,
                correct=g == letters,
                feedback=f"Yes! {letters} makes that sound." if g == letters else f"No, that's {g}.",
                distractor=why,
            )
            for g, why in shown
        ],
        answer=f"g_{letters}",
    )
