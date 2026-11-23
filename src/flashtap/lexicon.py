"""The things a round can ask about: a picture (an emoji for now), the word for it, the forms a sentence needs, and the
sound it starts with.

The words live in the `words` content pack (`src/flashtap/packs/words.toml`), with their graphemes and phonemes; this
module turns them into the `Thing`s the round generators use (`words()`, read once on first use). Plurals and articles are written per word where a rule
would be wrong ("sheep", "some grapes"). `onset` is the word's first GPC from the phonics inventory, or None when its
first sound is outside it; the Letters round uses only words whose first grapheme is one letter, so "What starts with
C?" never mixes /k/ (cat) with /tʃ/ (chicken).
"""

from dataclasses import dataclass
from functools import cache

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


@dataclass(frozen=True)
class Lexicon:
    everything: tuple[Thing, ...]

    def category(self, name: str) -> tuple[Thing, ...]:
        return tuple(t for t in self.everything if t.category == name)

    @property
    def animals(self) -> tuple[Thing, ...]:
        return self.category("animals")

    @property
    def food(self) -> tuple[Thing, ...]:
        return self.category("food")

    @property
    def vehicles(self) -> tuple[Thing, ...]:
        return self.category("vehicles")

    @property
    def shapes(self) -> tuple[Thing, ...]:
        return self.category("shapes")

    @property
    def matching_pools(self) -> tuple[tuple[Thing, ...], ...]:
        """Matching keeps a round inside one category, so a cow is never matched among buses."""
        return (self.animals, self.food, self.vehicles)

    @property
    def countable(self) -> tuple[Thing, ...]:
        """Pictures a learner can count in a row."""
        return self.animals + self.food

    @property
    def letter_words(self) -> tuple[Thing, ...]:
        """Words with a plain first sound, for Letters."""
        return tuple(t for t in self.animals + self.food if t.letter is not None)


@cache
def words() -> Lexicon:
    """The words from the packs, read on first use rather than at import: a broken pack must not stop
    `flashtap content check` from starting and naming what is wrong."""
    r = content.load()
    return Lexicon(
        tuple(
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
    )
