"""What the Content screen and `flashtap content list` show: the packs flattened into plain rows (`GET /api/content`).

Rows, not the registry's own models, so the web app gets one stable shape: each skill with its strand, domain, the
curriculum stages that map to it (labels only), the kinds of round that practise it and its edges both ways; each
objective with its skills or its reason for being out of scope; each phonics set with the words it makes decodable.
"""

from pydantic import BaseModel

from flashtap.content.registry import Registry


class PackRow(BaseModel):
    id: str
    version: int
    title: str
    status: str


class EdgeRow(BaseModel):
    skill: str  # the other end
    relation: str
    confidence: str
    source: str  # the Source's title
    note: str


class SkillRow(BaseModel):
    id: str
    title: str
    description: str
    domain: str  # the domain's title
    strand: str  # the strand's title
    stages: list[str]  # curriculum stage labels mapped to it; empty: no objective names it directly
    modes: list[str]  # kinds of round that practise it today
    needs: list[EdgeRow]  # edges into this skill (prerequisites, things that help)
    leads_to: list[EdgeRow]  # edges out of it
    misconceptions: list[str]  # titles


class ObjectiveRow(BaseModel):
    id: str
    curriculum: str
    stage: str
    area: str
    goal: str
    text: str
    skills: list[str]  # skill titles; empty when out of scope
    out_of_scope: str
    note: str


class GPCRow(BaseModel):
    grapheme: str
    phoneme: str
    example: str


class PhonicsSetRow(BaseModel):
    id: str
    title: str
    gpcs: list[GPCRow]
    words: list[str]  # words that become decodable once this set is taught


class PhonicsRow(BaseModel):
    id: str
    title: str
    dialect: str
    sets: list[PhonicsSetRow]


class ContentSummary(BaseModel):
    packs: list[PackRow]
    skills: list[SkillRow]
    objectives: list[ObjectiveRow]
    phonics: list[PhonicsRow]


def summarise(r: Registry, modes: dict[str, tuple[str, ...]]) -> ContentSummary:
    """`modes` maps a kind of round to the skill ids it practises (rounds.MODE_SKILLS)."""
    edges = r.edges

    def row(other: str, e_relation: str, confidence: str, provenance: str, note: str) -> EdgeRow:
        return EdgeRow(
            skill=r.skills[other].title,
            relation=e_relation,
            confidence=confidence,
            source=r.sources[provenance].title,
            note=note,
        )

    skills = [
        SkillRow(
            id=s.id,
            title=s.title,
            description=s.description,
            domain=r.domains[r.strands[s.strand].domain].title,
            strand=r.strands[s.strand].title,
            stages=r.stages_of(s.id),
            modes=sorted(m for m, ids in modes.items() if s.id in ids),
            needs=[row(e.source, e.relation, e.confidence, e.provenance, e.note) for e in edges if e.target == s.id],
            leads_to=[row(e.target, e.relation, e.confidence, e.provenance, e.note) for e in edges if e.source == s.id],
            misconceptions=[m.title for m in r.misconceptions.values() if s.id in m.skills],
        )
        for s in r.skills.values()
    ]
    objectives = [
        ObjectiveRow(
            id=o.id,
            curriculum=r.curricula[r.objective_curriculum[o.id]].title,
            stage=o.stage,
            area=o.area,
            goal=o.goal,
            text=o.text,
            skills=[r.skills[k].title for k in o.skills],
            out_of_scope=o.out_of_scope,
            note=o.note,
        )
        for o in r.objectives.values()
    ]
    phonics: list[PhonicsRow] = []
    for ph in r.phonics.values():
        decodable = {w.id: r.decodable_after(w, ph.id) for w in r.words.values()}
        phonics.append(
            PhonicsRow(
                id=ph.id,
                title=ph.title,
                dialect=ph.dialect,
                sets=[
                    PhonicsSetRow(
                        id=gs.id,
                        title=gs.title,
                        gpcs=[GPCRow(grapheme=g.grapheme, phoneme=g.phoneme, example=g.example) for g in gs.gpcs],
                        words=[r.words[w].word for w, at in decodable.items() if at == gs.id],
                    )
                    for gs in ph.sets
                ],
            )
        )
    packs = [PackRow(id=p.pack, version=p.version, title=p.title, status=p.status) for p in r.packs]
    return ContentSummary(packs=packs, skills=skills, objectives=objectives, phonics=phonics)
