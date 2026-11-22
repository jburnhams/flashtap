"""The things a round can ask about: a picture (an emoji for now), the word for it, and the forms a sentence needs.

Ported from the TypeScript library's `data/gameConfig.ts`, with what its string templates got wrong written down per word:
the plural ("sheep", not "sheeps") and the article ("an elephant", not "a elephant"). `initial` is the first sound's letter
for the Letters round, or None where the word does not start with the plain sound of its first letter (chicken, cheese):
"What starts with C?" must not mix /k/ and /tʃ/. A content pack with real phonemes replaces this (docs/plan.md, PR 2).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Thing:
    id: str
    picture: str  # an emoji today; an image path once packs carry art
    word: str  # lower case, as said in a sentence: "police car"
    category: str
    plural: str = ""  # empty: word + "s"
    article: str = ""  # empty: "an" before a vowel letter, else "a"
    initial: str | None = ""  # empty: the first letter; None: not used in the Letters round
    colour: str | None = None  # shapes only
    shape: str | None = None  # shapes only
    tags: tuple[str, ...] = field(default_factory=tuple[str, ...])

    @property
    def many(self) -> str:
        return self.plural or f"{self.word}s"

    @property
    def a(self) -> str:
        """The word with its indefinite article: "an elephant"."""
        return f"{self.article or ('an' if self.word[0] in 'aeiou' else 'a')} {self.word}"

    @property
    def letter(self) -> str | None:
        return None if self.initial is None else (self.initial or self.word[0]).upper()

    @property
    def label(self) -> str:
        """The word as a heading: "Police car"."""
        return self.word[0].upper() + self.word[1:]


ANIMALS = (
    Thing("sheep", "🐑", "sheep", "animals", plural="sheep"),
    Thing("cow", "🐄", "cow", "animals"),
    Thing("pig", "🐖", "pig", "animals"),
    Thing("horse", "🐎", "horse", "animals"),
    Thing("chicken", "🐓", "chicken", "animals", initial=None),
    Thing("dog", "🐕", "dog", "animals"),
    Thing("cat", "🐈", "cat", "animals"),
    Thing("duck", "🦆", "duck", "animals"),
    Thing("lion", "🦁", "lion", "animals"),
    Thing("tiger", "🐅", "tiger", "animals"),
    Thing("elephant", "🐘", "elephant", "animals"),
    Thing("monkey", "🐒", "monkey", "animals"),
)

FOOD = (
    Thing("apple", "🍎", "apple", "food"),
    Thing("banana", "🍌", "banana", "food"),
    Thing("grapes", "🍇", "grapes", "food", plural="grapes", article="some"),
    Thing("watermelon", "🍉", "watermelon", "food"),
    Thing("carrot", "🥕", "carrot", "food"),
    Thing("corn", "🌽", "corn", "food", plural="corn cobs", article="some"),
    Thing("pepper", "🌶️", "pepper", "food"),
    Thing("cheese", "🧀", "cheese", "food", plural="cheeses", article="some", initial=None),
)

VEHICLES = (
    Thing("car", "🚗", "car", "vehicles"),
    Thing("taxi", "🚕", "taxi", "vehicles"),
    Thing("bus", "🚌", "bus", "vehicles", plural="buses"),
    Thing("police", "🚓", "police car", "vehicles"),
    Thing("ambulance", "🚑", "ambulance", "vehicles"),
    Thing("fire", "🚒", "fire engine", "vehicles"),
    Thing("bicycle", "🚲", "bicycle", "vehicles"),
    Thing("aeroplane", "✈️", "aeroplane", "vehicles"),  # UK English (the spec's default dialect); was "Airplane"
    Thing("rocket", "🚀", "rocket", "vehicles"),
)


def _shape(colour: str, shape: str, picture: str) -> Thing:
    return Thing(f"{colour}_{shape}", picture, f"{colour} {shape}", "shapes", colour=colour, shape=shape)


SHAPES = (
    _shape("red", "circle", "🔴"),
    _shape("blue", "circle", "🔵"),
    _shape("green", "circle", "🟢"),
    _shape("yellow", "circle", "🟡"),
    _shape("red", "square", "🟥"),
    _shape("blue", "square", "🟦"),
    _shape("green", "square", "🟩"),
    _shape("orange", "square", "🟧"),
    _shape("white", "square", "⬜"),
    _shape("black", "square", "⬛"),
    _shape("orange", "diamond", "🔶"),
)

# Matching keeps a round inside one category, so a cow is never matched among buses.
MATCHING_POOLS = (ANIMALS, FOOD, VEHICLES)
# Counting needs pictures a child can count in a row; Letters needs words with a plain first sound.
COUNTABLE = ANIMALS + FOOD
LETTER_WORDS = tuple(t for t in ANIMALS + FOOD if t.letter is not None)
EVERYTHING = ANIMALS + FOOD + VEHICLES + SHAPES
