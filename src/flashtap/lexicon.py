"""The things a round can ask about: a picture (an emoji for now), the word for it, the forms a sentence needs, and the
sound it starts with.

The words live in the `words` content pack (`src/flashtap/packs/words.toml`), with their graphemes and phonemes; this
module turns them into the `Thing`s the round generators use. Plurals and articles are written per word where a rule
would be wrong ("sheep", "some grapes"). `onset` is the word's first GPC from the phonics inventory, or None when its
first sound is outside it; the Letters round uses only words whose first grapheme is one letter, so "What starts with
C?" never mixes /k/ (cat) with /tʃ/ (chicken).
"""

from dataclasses import dataclass

from flashtap import content
from flashtap.content.model import GPC


@dataclass(frozen=True)
class Thing:
    id: str
    picture: str  # an emoji today; an image path once packs carry art
    word: str  # lower case, as said in a sentence: "police car"
    category: str
    plural: str = ""  # empty: word + "s"
    article: str = ""  # empty: "an" before a vowel letter, else "a"
    onset: GPC | None = None  # the first sound, when the phonics inventory has it
    colour: str | None = None  # shapes only
    shape: str | None = None  # shapes only

    @property
    def many(self) -> str:
        return self.plural or f"{self.word}s"

    @property
    def a(self) -> str:
        """The word with its indefinite article: "an elephant"."""
        return f"{self.article or ('an' if self.word[0] in 'aeiou' else 'a')} {self.word}"

    @property
    def letter(self) -> str | None:
        """The capital letter for the Letters round: the first grapheme when it is a single letter, else None."""
        return self.onset.grapheme.upper() if self.onset and len(self.onset.grapheme) == 1 else None

    @property
    def label(self) -> str:
        """The word as a heading: "Police car"."""
        return self.word[0].upper() + self.word[1:]


def _things() -> tuple[Thing, ...]:
    r = content.load()
    return tuple(
        Thing(
            id=w.id,
            picture=w.picture,
            word=w.word,
            category=w.category,
            plural=w.plural,
            article=w.article,
            onset=r.onset(w),
            colour=w.colour or None,
            shape=w.shape or None,
        )
        for w in r.words.values()
        if w.picture
    )


EVERYTHING = _things()


def _category(name: str) -> tuple[Thing, ...]:
    return tuple(t for t in EVERYTHING if t.category == name)


ANIMALS = _category("animals")
FOOD = _category("food")
VEHICLES = _category("vehicles")
SHAPES = _category("shapes")

# Matching keeps a round inside one category, so a cow is never matched among buses.
MATCHING_POOLS = (ANIMALS, FOOD, VEHICLES)
# Counting needs pictures a child can count in a row; Letters needs words with a plain first sound.
COUNTABLE = ANIMALS + FOOD
LETTER_WORDS = tuple(t for t in ANIMALS + FOOD if t.letter is not None)
