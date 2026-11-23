"""Reading the packs and checking them as a whole: the Ontology Registry of spec §14.

`read(folder)` parses every `*.toml` file and returns the packs with any problems found on the way; `Registry` indexes
them; `check(registry)` finds what no single entry can show: an id used twice, an edge or mapping that points nowhere, a
`prerequisite_strong` or `part_of` cycle, a skill parameter outside its dimension, a word whose graphemes do not spell
it. `load()` is what the app uses: the packaged packs, read once, refused if any problem is found, so a bad pack stops
the server at start and fails `flashtap content check` in CI rather than reaching a learner.

TOML, not YAML: `tomllib` is in the standard library (no new dependency, no implicit typing such as `no` read as false),
and pydantic checks every table.
"""

import tomllib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from flashtap.content.model import (
    GPC,
    Curriculum,
    Dimension,
    Domain,
    Edge,
    Misconception,
    Objective,
    Pack,
    Phonics,
    Relation,
    Skill,
    Source,
    Strand,
    Word,
)

PACKS = Path(__file__).resolve().parent.parent / "packs"


@dataclass(frozen=True)
class Problem:
    where: str  # the pack file, or the id the problem is about
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


class ContentError(ValueError):
    """The packs do not pass `check`: a content bug, caught before any round is built from it."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} content problem(s); first: {problems[0]}")


def read(folder: Path = PACKS) -> tuple[list[Pack], list[Problem]]:
    packs: list[Pack] = []
    problems: list[Problem] = []
    files = sorted(folder.glob("*.toml"))
    if not files:
        problems.append(Problem(str(folder), "no *.toml packs"))
    for f in files:
        try:
            packs.append(Pack.model_validate(tomllib.loads(f.read_text(encoding="utf-8"))))
        except tomllib.TOMLDecodeError as e:
            problems.append(Problem(f.name, f"not TOML: {e}"))
        except ValidationError as e:
            for err in e.errors():
                at = ".".join(str(p) for p in err["loc"])
                problems.append(Problem(f.name, f"{at}: {err['msg']}" if at else err["msg"]))
    return packs, problems


@dataclass
class Registry:
    packs: list[Pack]
    sources: dict[str, Source] = field(default_factory=dict[str, Source])
    domains: dict[str, Domain] = field(default_factory=dict[str, Domain])
    strands: dict[str, Strand] = field(default_factory=dict[str, Strand])
    dimensions: dict[str, Dimension] = field(default_factory=dict[str, Dimension])
    skills: dict[str, Skill] = field(default_factory=dict[str, Skill])
    misconceptions: dict[str, Misconception] = field(default_factory=dict[str, Misconception])
    phonics: dict[str, Phonics] = field(default_factory=dict[str, Phonics])
    words: dict[str, Word] = field(default_factory=dict[str, Word])
    curricula: dict[str, Curriculum] = field(default_factory=dict[str, Curriculum])
    objectives: dict[str, Objective] = field(default_factory=dict[str, Objective])
    objective_curriculum: dict[str, str] = field(default_factory=dict[str, str])
    duplicates: list[Problem] = field(default_factory=list[Problem])

    def __post_init__(self) -> None:
        seen: dict[str, str] = {}  # one id space across every kind, so an id names one thing wherever it is quoted

        def add(kind: str, table: dict[str, Any], key: str, item: object, pack: str) -> None:
            if key in seen:
                self.duplicates.append(Problem(key, f"id used twice ({seen[key]}, and {kind} in {pack})"))
                return
            seen[key] = f"{kind} in {pack}"
            table[key] = item

        for p in self.packs:
            for s in p.sources:
                add("source", self.sources, s.id, s, p.pack)
            for d in p.domains:
                add("domain", self.domains, d.id, d, p.pack)
            for st in p.strands:
                add("strand", self.strands, st.id, st, p.pack)
            for dim in p.dimensions:
                add("dimension", self.dimensions, dim.id, dim, p.pack)
            for sk in p.skills:
                add("skill", self.skills, sk.id, sk, p.pack)
            for m in p.misconceptions:
                add("misconception", self.misconceptions, m.id, m, p.pack)
            for ph in p.phonics:
                add("phonics sequence", self.phonics, ph.id, ph, p.pack)
                for gs in ph.sets:
                    add("phonics set", {}, gs.id, gs, p.pack)
            for w in p.words:
                add("word", self.words, w.id, w, p.pack)
            if p.curriculum:
                add("curriculum", self.curricula, p.curriculum.id, p.curriculum, p.pack)
                for o in p.objectives:
                    add("objective", self.objectives, o.id, o, p.pack)
                    self.objective_curriculum[o.id] = p.curriculum.id

    @property
    def edges(self) -> list[Edge]:
        """Every skill edge, turned so `source` -relation-> `target` whichever end it was written on."""
        out: list[Edge] = []
        for sk in self.skills.values():
            for e in sk.edges:
                src, tgt = (sk.id, e.to) if e.to is not None else (e.from_ or "", sk.id)
                out.append(
                    Edge(
                        source=src,
                        target=tgt,
                        relation=e.relation,
                        confidence=e.confidence,
                        provenance=e.source,
                        note=e.note,
                    )
                )
        return out

    def gpcs(self) -> list[GPC]:
        """The GPC inventory: every correspondence in any sequence, once each."""
        seen: dict[str, GPC] = {}
        for ph in self.phonics.values():
            for gs in ph.sets:
                for g in gs.gpcs:
                    seen.setdefault(g.key, g)
        return list(seen.values())

    def resolve(self, segment: str) -> GPC | None:
        """A word segment ("s", or "th:ð" where a grapheme has two sounds) as one GPC; None if unknown or ambiguous."""
        grapheme, _, phoneme = segment.partition(":")
        found = [g for g in self.gpcs() if g.grapheme == grapheme and (not phoneme or g.phoneme == phoneme)]
        return found[0] if len(found) == 1 else None

    def word_gpcs(self, w: Word) -> list[GPC]:
        """The word's GPCs in order: all of them when it is segmented, its first only when it gives an onset."""
        parts = w.segments or ((w.onset,) if w.onset else ())
        return [g for g in (self.resolve(s) for s in parts) if g is not None]

    def onset(self, w: Word) -> GPC | None:
        gs = self.word_gpcs(w)
        return gs[0] if gs else None

    def decodable_after(self, w: Word, sequence: str) -> str | None:
        """The first set of `sequence` after which every GPC in the segmented word has been taught, or None."""
        if not w.segments:
            return None
        taught: set[str] = set()
        needed = {g.key for g in self.word_gpcs(w)}
        if len(needed) == 0:
            return None
        for gs in self.phonics[sequence].sets:
            taught |= {g.key for g in gs.gpcs}
            if needed <= taught:
                return gs.id
        return None

    def stages_of(self, skill: str) -> list[str]:
        """The curriculum stage labels whose objectives map to `skill`. Labels only: nothing is gated on them."""
        return sorted({o.stage for o in self.objectives.values() if skill in o.skills})


def check(r: Registry) -> list[Problem]:
    problems = list(r.duplicates)

    def need(where: str, what: str, key: str, table: Mapping[str, object]) -> None:
        if key not in table:
            problems.append(Problem(where, f"{what} {key!r} does not exist"))

    for st in r.strands.values():
        need(st.id, "domain", st.domain, r.domains)
    for sk in r.skills.values():
        need(sk.id, "strand", sk.strand, r.strands)
        for dim_id, values in sk.dimensions.items():
            dim = r.dimensions.get(dim_id)
            if dim is None:
                problems.append(Problem(sk.id, f"dimension {dim_id!r} does not exist"))
                continue
            problems.extend(Problem(sk.id, m) for m in _dimension_values(dim, values))
    for e in r.edges:
        where = e.source if e.source in r.skills else e.target  # the end that exists: the skill it was written on
        for end in (e.source, e.target):
            need(where, "edge end", end, r.skills)
        need(where, "source", e.provenance, r.sources)
        if e.source == e.target:
            problems.append(Problem(where, f"{e.relation} edge to itself"))
    seen_edges: set[tuple[str, str, Relation]] = set()
    for e in r.edges:
        k = (e.source, e.target, e.relation)
        if k in seen_edges:
            problems.append(Problem(e.target, f"{e.relation} from {e.source} written twice"))
        seen_edges.add(k)
    for rel in (Relation.PREREQUISITE_STRONG, Relation.PART_OF):
        cycle = _cycle([(e.source, e.target) for e in r.edges if e.relation is rel])
        if cycle:
            problems.append(Problem(cycle[0], f"{rel} cycle: {' -> '.join(cycle)}"))
    for m in r.misconceptions.values():
        need(m.id, "source", m.source, r.sources)
        for s in m.skills:
            need(m.id, "skill", s, r.skills)
    for ph in r.phonics.values():
        need(ph.id, "source", ph.source, r.sources)
        keys = [g.key for gs in ph.sets for g in gs.gpcs]
        problems.extend(Problem(ph.id, f"{k} taught twice") for k in sorted({k for k in keys if keys.count(k) > 1}))
    problems.extend(_words(r))
    for c in r.curricula.values():
        need(c.id, "source", c.source, r.sources)
    for o in r.objectives.values():
        stages = {s.id for s in r.curricula[r.objective_curriculum[o.id]].stages}
        if o.stage not in stages:
            problems.append(
                Problem(o.id, f"stage {o.stage!r} is not one of its curriculum's ({', '.join(sorted(stages))})")
            )
        for s in o.skills:
            need(o.id, "skill", s, r.skills)
    return problems


def _dimension_values(dim: Dimension, values: tuple[int, int] | tuple[str, ...]) -> list[str]:
    if dim.kind == "range":
        if len(values) != 2:
            return [f"{dim.id} is a range: give [low, high]"]
        lo, hi = values
        if not isinstance(lo, int) or not isinstance(hi, int):
            return [f"{dim.id} is a range: give [low, high]"]
        low, high = dim.low or 0, dim.high or 0  # Dimension's validator: a range has both
        if not low <= lo <= hi <= high:
            return [f"{dim.id} [{lo}, {hi}] is outside {low} to {high} or reversed"]
        return []
    bad = [str(v) for v in values if v not in dim.values]
    if bad or not values:
        return [f"{dim.id}: {', '.join(bad) or 'no values'} (allowed: {', '.join(dim.values)})"]
    return []


def _words(r: Registry) -> list[Problem]:
    problems: list[Problem] = []
    pictures: dict[str, str] = {}
    for w in r.words.values():
        if w.picture:
            if w.picture in pictures:
                problems.append(Problem(w.id, f"picture {w.picture} is also {pictures[w.picture]}"))
            pictures[w.picture] = w.id
        for s in w.segments or ((w.onset,) if w.onset else ()):
            if r.resolve(s) is None:
                problems.append(
                    Problem(w.id, f"segment {s!r} is not one GPC in the inventory (write it as grapheme:phoneme)")
                )
        if w.segments:
            spelt = "".join(s.partition(":")[0] for s in w.segments)
            if spelt != _spelling(w.word):
                problems.append(Problem(w.id, f"segments spell {spelt!r}, not {w.word!r}"))
        elif w.onset and not _spelling(w.word).startswith(w.onset.partition(":")[0]):
            problems.append(Problem(w.id, f"onset {w.onset!r} is not how {w.word!r} starts"))
    return problems


def _spelling(word: str) -> str:
    return word.replace(" ", "")


def _cycle(edges: list[tuple[str, str]]) -> list[str]:
    """One cycle in the directed graph, as a path that returns to its start; [] when there is none."""
    out: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        out[a].append(b)
    state: dict[str, int] = {}  # 1: on the current path, 2: finished
    path: list[str] = []

    def visit(n: str) -> list[str]:
        state[n] = 1
        path.append(n)
        for m in out[n]:
            if state.get(m) == 1:
                return [*path[path.index(m) :], m]
            if m not in state:
                found = visit(m)
                if found:
                    return found
        state[n] = 2
        path.pop()
        return []

    for n in sorted(out):
        if n not in state:
            found = visit(n)
            if found:
                return found
    return []


def build(folder: Path = PACKS) -> tuple[Registry, list[Problem]]:
    packs, problems = read(folder)
    r = Registry(packs)
    return r, problems + check(r)


@cache
def load(folder: Path = PACKS) -> Registry:
    """The packs in `folder` (the packaged ones by default), checked. Raises ContentError on any problem; read once."""
    r, problems = build(folder)
    if problems:
        raise ContentError(problems)
    return r
