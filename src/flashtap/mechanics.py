"""What a round is, whatever kind it is: the shape the server sends and the rules every round must pass.

A round is built by a template (`rounds.TEMPLATES`) from (kind, version, choices, seed) and drawn by one of eight
mechanics. Two families, because the browser answers them in two ways:

- **Choose** (one tap answers): `select_one` (find the named picture), `fill_missing` (the number missing from a
  run), `brief_exposure` (a group shown for a moment, then hidden: how many?), `audio_respond` (a word is heard, not
  shown: which letter does it start with?). The round has `options`, exactly one `correct`.
- **Place** (an arrangement answers, checked when the learner says it is done): `give_n` (put N in the basket),
  `sequence` (put in order), `match_pairs` (each capital to its small letter), `sort` (pictures into groups). The round
  has `pieces` and `places`; each place says which pieces it `takes` and how many it `holds`. The arrangement is right
  when every place holds exactly that many, all of them pieces it takes. That one rule covers all four: a basket that
  takes every apple and holds 4; a slot per position that takes one numeral and holds 1; a group that takes its
  pictures and holds them all.

Every round names the skills it gives evidence on and in what role (the spec's Q-matrix, §8): `primary`, the skill
the template is written to assess; `secondary`, a skill also exercised, weaker evidence; `confound`, a skill needed to
answer that could explain an error on its own (reading the numeral in a counting round). The learner model (plan PR
4) credits a right answer to primary and secondary skills, and does not count a wrong one against the primary alone
while a confound is unobserved.

Every wrong option names the generator that chose it (`distractor`: `near_number`, `reversal`, `confusable_grapheme`,
`phonological_neighbour`, `same_category`, `random`), so a pattern of taps can be read as a misconception (a 9 for
six is a reversal, not a miscount).
"""

from enum import StrEnum

from pydantic import BaseModel, Field
from strata_python.contracts import ApiModel

SEED_LIMIT = 2**31  # seeds fit a JavaScript number and a 32-bit column


class Mode(StrEnum):
    """A kind of round: one template each, plus Mixed. The first five are the original rounds (their ids are kept, so
    saved settings still name them)."""

    MATCHING = "matching"
    COLOURS = "colours"
    SHAPES = "shapes"
    LETTERS = "letters"
    COUNTING = "counting"
    MISSING = "missing"
    QUICK_LOOK = "quick_look"
    LISTEN = "listen"
    GIVE = "give"
    ORDER = "order"
    CAPITALS = "capitals"
    SORT_SOUNDS = "sort_sounds"
    MIXED = "mixed"


class Mechanic(StrEnum):
    SELECT_ONE = "select_one"
    FILL_MISSING = "fill_missing"
    BRIEF_EXPOSURE = "brief_exposure"
    AUDIO_RESPOND = "audio_respond"
    GIVE_N = "give_n"
    SEQUENCE = "sequence"
    MATCH_PAIRS = "match_pairs"
    SORT = "sort"


CHOOSE = frozenset({Mechanic.SELECT_ONE, Mechanic.FILL_MISSING, Mechanic.BRIEF_EXPOSURE, Mechanic.AUDIO_RESPOND})
PLACE = frozenset({Mechanic.GIVE_N, Mechanic.SEQUENCE, Mechanic.MATCH_PAIRS, Mechanic.SORT})


class QRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONFOUND = "confound"


class SkillRole(BaseModel):
    skill: str  # a skill id from the content packs
    role: QRole


class Option(BaseModel):
    id: str
    picture: str  # what the tile shows: an emoji, a numeral or a letter
    word: str  # what it is, for a screen reader; never printed on the tile, which would give the answer away
    correct: bool
    feedback: str  # said when this option is tapped: the success message on the right one
    distractor: str = ""  # the generator that chose a wrong option; empty on the right one


class Piece(BaseModel):
    id: str
    picture: str
    word: str


class Place(BaseModel):
    id: str
    picture: str  # what the place shows as its target: "🧺", "A", "s"; empty for a position, drawn as its word
    word: str  # "the basket", "first", "A"
    takes: list[str]  # the piece ids that belong here
    holds: int = Field(ge=1)  # how many it must hold when the arrangement is right


class Round(ApiModel):  # every field is always sent, so the schema (and the web app's generated type) needs no `?`
    mode: Mode  # the kind actually played (never MIXED)
    version: int = Field(ge=1)  # the template's version: with mode, choices and seed it rebuilds the round exactly
    choices: int
    seed: int = Field(ge=0, lt=SEED_LIMIT)
    mechanic: Mechanic
    skills: list[SkillRole]
    prompt: str  # shown as the heading: "Find the cow", "Listen, then tap the letter"
    say: str  # said aloud; differs from prompt where printing it would give the answer to a reader
    show: str = ""  # the big picture or word above the answer: "🐄", "RED", "1 2 _ 4", "🍎 🍎 🍎"; empty for none
    exposure_ms: int | None = None  # brief exposure: `show` is hidden after this long
    options: list[Option] = Field(default_factory=list[Option])  # a factory: ruff cannot tell ApiModel is pydantic
    answer: str = ""  # a choose round's right option id
    pieces: list[Piece] = Field(default_factory=list[Piece])
    places: list[Place] = Field(default_factory=list[Place])
    done_feedback: str = ""  # a place round: said when the arrangement is right
    tries: int | None = None  # taps (or checks) allowed before the round counts as missed; None: no limit


class InvalidRound(ValueError):
    """A generated round that breaks a rule `check` enforces: a bug in a generator, never a learner's mistake."""


MIN_OPTIONS = 2


def check(r: Round) -> Round:
    """Refuse a round whose answer is not one and unmistakable (the 1,000-seed validator suite runs this on every
    template; `rounds.generate` runs it on every round served)."""
    where = f"{r.mode} v{r.version} seed {r.seed}"
    if not any(s.role is QRole.PRIMARY for s in r.skills):
        raise InvalidRound(f"{where}: no primary skill")
    if r.mechanic in CHOOSE:
        _check_choose(r, where)
    else:
        _check_place(r, where)
    if r.mechanic is Mechanic.BRIEF_EXPOSURE and not (r.exposure_ms and r.show):
        raise InvalidRound(f"{where}: a brief exposure needs something to show and how long")
    if r.mechanic is not Mechanic.BRIEF_EXPOSURE and r.exposure_ms is not None:
        raise InvalidRound(f"{where}: only a brief exposure hides what it shows")
    return r


def _check_choose(r: Round, where: str) -> None:
    ids = [o.id for o in r.options]
    right = [o for o in r.options if o.correct]
    if r.pieces or r.places:
        raise InvalidRound(f"{where}: a choose round has no pieces or places")
    if len(right) != 1:
        raise InvalidRound(f"{where}: {len(right)} right answers")
    if right[0].id != r.answer:
        raise InvalidRound(f"{where}: answer {r.answer} is not the right option {right[0].id}")
    if len(set(ids)) != len(ids) or len({o.picture for o in r.options}) != len(ids):
        raise InvalidRound(f"{where}: repeated options")
    if len(ids) < MIN_OPTIONS:
        raise InvalidRound(f"{where}: only {len(ids)} options")
    if any(not o.correct and not o.distractor for o in r.options):
        raise InvalidRound(f"{where}: a wrong option with no distractor named")


def _check_place(r: Round, where: str) -> None:
    pieces = {p.id: p for p in r.pieces}
    if r.options or r.answer:
        raise InvalidRound(f"{where}: a place round has no options")
    if len(pieces) != len(r.pieces) or len({s.id for s in r.places}) != len(r.places):
        raise InvalidRound(f"{where}: repeated ids")
    if not r.places or len(r.pieces) < MIN_OPTIONS:
        raise InvalidRound(f"{where}: too few pieces or places")
    if len({(s.picture, s.word) for s in r.places}) != len(r.places):
        raise InvalidRound(f"{where}: two places look the same")
    home: dict[str, str] = {}
    for s in r.places:
        for k in s.takes:
            if k not in pieces:
                raise InvalidRound(f"{where}: {s.id} takes {k}, which is not a piece")
            if k in home:
                # A piece two places take would make more than one arrangement right.
                raise InvalidRound(f"{where}: {k} belongs in {home[k]} and {s.id}")
            home[k] = s.id
        if s.holds > len(s.takes):
            raise InvalidRound(f"{where}: {s.id} must hold {s.holds} but takes {len(s.takes)}")
    # Pieces that look the same cannot be told apart, so they must belong in the same place (or none).
    by_look: dict[tuple[str, str], set[str | None]] = {}
    for p in r.pieces:
        by_look.setdefault((p.picture, p.word), set()).add(home.get(p.id))
    if any(len(homes) > 1 for homes in by_look.values()):
        raise InvalidRound(f"{where}: pieces that look the same belong in different places")
    if not r.done_feedback:
        raise InvalidRound(f"{where}: no words for a right arrangement")


def arranged_right(r: Round, placement: dict[str, str]) -> bool:
    """Whether `placement` (piece id -> place id; a piece not in it is unplaced) answers a place round."""
    for s in r.places:
        inside = [k for k, at in placement.items() if at == s.id]
        if len(inside) != s.holds or any(k not in s.takes for k in inside):
            return False
    return True
