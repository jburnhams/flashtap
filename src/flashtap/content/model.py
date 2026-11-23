"""The shapes a content pack is written in (spec §3, "Ontology architecture"): what each TOML table may hold.

These models check one entry on its own (types, required fields, id format). What needs the whole registry (an edge's
other end exists, `prerequisite_strong` has no cycle, every objective is mapped or set aside) is `content.check`.

Why these shapes:

- **Skills, not ages or years.** A skill is a capability plus the parameter ranges it is defined over (spec §3: "core
  capability + parameters", never one skill per Cartesian combination). Nothing here holds an age, a year group or a
  stage: curriculum stages are labels on objectives (`Curriculum.stages`), and an objective points at skills. A skill
  from a later stage is one more `[[skills]]` entry and, if a new curriculum maps it, one more curriculum pack; no
  schema change.
- **Typed edges with provenance.** Every edge names its relation, its confidence and the source it rests on, because
  the spec warns that ordering is often probabilistic and never to be inferred from curriculum order alone (§2, §3).
  An edge is written on either end (`to` or `from`) so an author can keep a skill's prerequisites with the skill.
- **Phonics as data.** A phonics sequence is a list of sets of grapheme-phoneme correspondences in IPA (UK English by
  default, §5). It is configurable (another programme is another sequence), but each one is kept in its own order.
- **Words with their sounds.** A word carries its spelling split into graphemes, each resolved to a phoneme through
  the GPC inventory, so "what starts with /k/" and "decodable after set 3" are computed, not hand-kept lists.
"""

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")


def _id(v: str) -> str:
    if not _ID.match(v):
        raise ValueError(f"{v!r} is not an id: lower case words joined by dots, such as maths.counting.objects")
    return v


Id = Annotated[str, AfterValidator(_id)]


class Strict(BaseModel):
    """Every content model refuses keys it does not know: a misspelt key in a pack is an error, not a silent default."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Source(Strict):
    id: Id
    title: str
    url: str = Field(pattern=r"^https://")
    publisher: str = ""
    edition: str = ""  # the version read: "Effective 1 September 2026"
    checked: date | None = None  # when someone compared what the packs claim with the source itself; None: not yet


class Domain(Strict):
    id: Id
    title: str


class Strand(Strict):
    id: Id
    domain: Id
    title: str


class Dimension(Strict):
    """A parameter a skill is defined over (spec §4-§6): a number range, a set of representations, an ordered scale."""

    id: Id
    title: str
    kind: Literal["range", "set", "ordered"]
    low: int | None = None  # range only: the smallest value any skill may use
    high: int | None = None
    values: tuple[str, ...] = ()  # set and ordered: every value a skill may use (ordered: easiest first)
    description: str = ""

    @model_validator(mode="after")
    def _kind_fits(self) -> "Dimension":
        if self.kind == "range":
            if self.low is None or self.high is None or self.low > self.high or self.values:
                raise ValueError(f"dimension {self.id}: a range needs low <= high and no values")
        elif not self.values or self.low is not None or self.high is not None:
            raise ValueError(f"dimension {self.id}: a {self.kind} needs values and no low or high")
        elif len(set(self.values)) != len(self.values):
            raise ValueError(f"dimension {self.id}: repeated values")
        return self


class Relation(StrEnum):
    """Skill-to-skill relations from spec §3. The others it lists live elsewhere: `maps_to_curriculum` is an objective's
    `skills`, `misconception_of` is a misconception's `skills`, and the mechanic relations (`teaches`, `practises`,
    `assesses_*`) arrive with the mechanics (plan PR 3)."""

    PREREQUISITE_STRONG = "prerequisite_strong"  # normally necessary for the target; ask for evidence of it first
    FACILITATES = "facilitates"  # helps, not required
    PART_OF = "part_of"  # taxonomy, not order
    RELATED_TO = "related_to"  # overlap, no causal claim
    CONFOUNDED_BY = "confounded_by"  # the other skill can explain errors on this one


class Confidence(StrEnum):
    # Words, not a probability: these are judgements from guidance and literature, and a number would claim precision
    # nobody has measured. The learner model (plan PR 4) estimates from evidence instead.
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EdgeSpec(Strict):
    """An edge as written on a skill: exactly one of `to` (this skill -> other) or `from` (other -> this skill)."""

    relation: Relation
    to: Id | None = None
    from_: Id | None = Field(default=None, alias="from")
    confidence: Confidence
    source: Id
    note: str = ""

    @model_validator(mode="after")
    def _one_end(self) -> "EdgeSpec":
        if (self.to is None) == (self.from_ is None):
            raise ValueError("an edge names exactly one of to or from")
        return self


class Edge(Strict):
    """A directed edge: `source` -relation-> `target`. For `prerequisite_strong`, `source` is the prerequisite."""

    source: str
    target: str
    relation: Relation
    confidence: Confidence
    provenance: str  # a Source id
    note: str = ""


DimensionValues = tuple[int, int] | tuple[str, ...]  # a range's [low, high], or the set or ordered values that apply


class Skill(Strict):
    id: Id
    title: str
    strand: Id
    description: str = ""
    dimensions: dict[str, DimensionValues] = Field(default_factory=dict[str, DimensionValues])
    edges: tuple[EdgeSpec, ...] = ()


class Misconception(Strict):
    """A named error pattern (spec §3 `misconception_of`): what it looks like and how to tell it from a slip."""

    id: Id
    title: str
    skills: tuple[Id, ...] = Field(min_length=1)
    signs: str  # what a learner does
    probe: str  # an item that separates it from a slip
    source: Id


class GPC(Strict):
    """One grapheme-phoneme correspondence: the letters and the sound (IPA, UK English) they stand for."""

    # Letters only. Split digraphs ("a_e" in "cake") arrive with Phase 5: a segment list cannot place their second
    # letter after the next consonant, so they will need a field of their own then.
    grapheme: str = Field(pattern=r"^[a-z]+$")
    phoneme: str = Field(min_length=1)
    example: str = ""  # a word that shows it: "sun"

    @property
    def key(self) -> str:
        return f"{self.grapheme}:{self.phoneme}"


class GPCSet(Strict):
    id: Id
    title: str
    gpcs: tuple[GPC, ...] = Field(min_length=1)


class Phonics(Strict):
    """A phonics sequence: sets taught in this order. Several may exist; a learner follows one (spec §5)."""

    id: Id
    title: str
    dialect: str = "en-GB"
    source: Id
    sets: tuple[GPCSet, ...] = Field(min_length=1)


class Word(Strict):
    """A word a round can use. `segments` splits the spelling into graphemes; a bare grapheme resolves through the GPC
    inventory when only one correspondence has it, otherwise it is written "th:ð". A word with no segmentation yet gives
    only its `onset`; a word whose first sound is outside the inventory gives neither and is left out of sound rounds."""

    id: Id
    word: str  # lower case, as said in a sentence: "police car"
    category: str
    picture: str = ""  # an emoji for now; none: the word cannot be shown as a picture
    plural: str = ""  # empty: word + "s"
    article: str = ""  # empty: "an" before a vowel letter, else "a"
    segments: tuple[str, ...] = ()
    onset: str = ""
    colour: str = ""  # shapes only
    shape: str = ""

    @model_validator(mode="after")
    def _one_way(self) -> "Word":
        if self.segments and self.onset:
            raise ValueError(f"word {self.id}: give segments or onset, not both (the onset comes from the segments)")
        return self


class Objective(Strict):
    """One curriculum statement. It maps to skills, or says why Flashtap leaves it out: never neither (spec §18 P0)."""

    id: Id
    stage: Id
    area: str
    goal: str
    text: str
    skills: tuple[Id, ...] = ()
    out_of_scope: str = ""
    note: str = ""

    @model_validator(mode="after")
    def _mapped_or_not(self) -> "Objective":
        if bool(self.skills) == bool(self.out_of_scope):
            raise ValueError(f"objective {self.id}: give skills or out_of_scope (exactly one)")
        return self


class Stage(Strict):
    id: Id
    title: str


class Curriculum(Strict):
    id: Id
    title: str
    source: Id
    stages: tuple[Stage, ...] = Field(min_length=1)


class Pack(Strict):
    """One TOML file under `packs/`. Every section is optional; ids are global across all packs."""

    pack: Id
    version: int = Field(ge=1)  # raise it with every change to the pack's content, so evidence can name what it saw
    title: str
    status: Literal["draft", "reviewed"]  # draft: written from sources, not yet checked by a person who teaches it
    sources: tuple[Source, ...] = ()
    domains: tuple[Domain, ...] = ()
    strands: tuple[Strand, ...] = ()
    dimensions: tuple[Dimension, ...] = ()
    skills: tuple[Skill, ...] = ()
    misconceptions: tuple[Misconception, ...] = ()
    phonics: tuple[Phonics, ...] = ()
    words: tuple[Word, ...] = ()
    curriculum: Curriculum | None = None
    objectives: tuple[Objective, ...] = ()

    @model_validator(mode="after")
    def _objectives_need_a_curriculum(self) -> "Pack":
        if self.objectives and self.curriculum is None:
            raise ValueError(f"pack {self.pack}: objectives need a [curriculum] table in the same pack")
        return self
