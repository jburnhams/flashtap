"""The round templates' bodies: one function per kind of round, from a seeded `random.Random` and the number of
choices to what the round shows and its answer. What a template is (its kind, version, mechanic and skills) is
declared once in `flashtap.rounds.TEMPLATES`, which builds the `Round` around a body and checks it.

`choose.py` holds the one-tap kinds, `place.py` the ones answered by an arrangement.
"""

from dataclasses import dataclass, field

from flashtap.mechanics import Option, Piece, Place


@dataclass(frozen=True)
class Body:
    prompt: str
    say: str = ""  # empty: say the prompt
    show: str = ""
    exposure_ms: int | None = None
    peeks: int = 0  # brief exposure: looks again the learner may ask for once it hides
    options: list[Option] = field(default_factory=list[Option])
    answer: str = ""
    pieces: list[Piece] = field(default_factory=list[Piece])
    places: list[Place] = field(default_factory=list[Place])
    done_feedback: str = ""
