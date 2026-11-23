"""What the evidence says about a learner, for a grown-up: estimates per skill, a reporting state, and why each attempt
counted or did not. Everything here is computed from the event log on each read, never stored, so a rebuild from the
log (an export, or the database after a restore) gives the same answer; `differences` checks that.

Reporting states (spec §13) are derived labels, not the model's state: the model's state is the estimates.

- `unobserved`: no attempt has touched the skill. Kept apart from every other state: no evidence is not "not mastered".
- `introduced`: touched, but fewer than `ENOUGH` counted first answers.
- `emerging`: enough counted answers, but BKT's P(known) is below `INDEPENDENT`.
- `independent`: BKT's P(known) at least `INDEPENDENT` and the rule baseline's recent share at least `RECENT`, with
  at least `ENOUGH` right answers in rounds written to assess this skill (primary). Right answers where it was only
  secondary or a confound move the estimates but cannot make a skill independent alone: a right answer to a task that
  needs several skills is not proof of each of them (§8).
- `generalised`: independent, and right in at least two mechanics (a tap and an arrangement, say), so it is not one
  game learnt by heart (§11: "strong skill in one mechanic only").
- `retained`: generalised, right again at least `RETAINED_AFTER` after its first counted right answer, and the latest
  counted answer right.

The thresholds are experimental defaults (§13 asks for "no global accuracy threshold" in the end: P3 replaces them with
uncertainty and transfer probes once there is data).
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel

from flashtap import rounds
from flashtap.learners.estimators import BAYES, ESTIMATORS, RULE, Estimate, model_id
from flashtap.learners.evidence import Event, Use, observations, uses
from flashtap.mechanics import Mode

ENOUGH = 3
INDEPENDENT = 0.85
RECENT = 0.8  # 4 of the last 5
RETAINED_AFTER = timedelta(days=7)


class State(StrEnum):
    UNOBSERVED = "unobserved"
    INTRODUCED = "introduced"
    EMERGING = "emerging"
    INDEPENDENT = "independent"
    GENERALISED = "generalised"
    RETAINED = "retained"


class SkillInfo(BaseModel):
    """A skill as the packs name it."""

    id: str
    title: str
    domain: str
    strand: str


class SkillReport(BaseModel):
    skill: str
    title: str
    domain: str
    strand: str
    state: State
    estimates: list[Estimate]  # one per estimator, BKT first; empty when unobserved (a prior is not evidence)
    counted: int  # first answers counted for this skill
    right: int  # of which right
    held: int  # attempts that touched it but did not count (a wrong answer on a secondary skill, or held back)
    mechanics: list[str]  # the mechanics of its counted right answers
    last_seen: datetime | None  # the latest attempt that touched it


class ModelInfo(BaseModel):
    model: str
    description: str


MODELS = [ModelInfo(model=model_id(e), description=e.description) for e in ESTIMATORS]


def state_of(counted: Sequence[Use], estimates: Mapping[str, Estimate], touched: bool) -> State:
    if not touched:
        return State.UNOBSERVED
    bkt, rule = estimates.get(model_id(BAYES)), estimates.get(model_id(RULE))
    if len(counted) < ENOUGH or bkt is None or rule is None:
        return State.INTRODUCED
    rights = [u for u in counted if u.event.first_correct]
    primary = [u for u in rights if u.role == "primary"]
    if bkt.p < INDEPENDENT or rule.p < RECENT or len(primary) < ENOUGH:
        return State.EMERGING
    if len({u.event.mechanic for u in rights}) < 2:
        return State.INDEPENDENT
    first = rights[0].event.presented_at
    if counted[-1].event.first_correct and any(u.event.presented_at - first >= RETAINED_AFTER for u in rights):
        return State.RETAINED
    return State.GENERALISED


def skill_reports(events: Iterable[Event], skills: Sequence[SkillInfo]) -> list[SkillReport]:
    """One report per skill in `skills`, then any skill the log names that the packs no longer do (by its id)."""
    info = {s.id: s for s in skills}
    by_skill = uses(events, {s.id: s.title for s in skills})
    known = [*skills, *(SkillInfo(id=k, title=k, domain="", strand="") for k in sorted(by_skill) if k not in info)]
    out: list[SkillReport] = []
    for s in known:
        all_uses = by_skill.get(s.id, [])
        live = [u for u in all_uses if u.event.struck is None]
        counted = [u for u in live if u.counted]
        obs = observations(counted)
        estimates = [e.estimate(obs) for e in ESTIMATORS] if counted else []
        out.append(
            SkillReport(
                skill=s.id,
                title=s.title,
                domain=s.domain,
                strand=s.strand,
                state=state_of(counted, {e.model: e for e in estimates}, bool(live)),
                estimates=estimates,
                counted=len(counted),
                right=sum(u.event.first_correct for u in counted),
                held=len(live) - len(counted),
                mechanics=sorted({u.event.mechanic for u in counted if u.event.first_correct}),
                last_seen=max((u.event.presented_at for u in live), default=None),
            )
        )
    return out


class EvidenceRow(BaseModel):
    """One attempt as it bears on one skill: the provenance behind an estimate."""

    event_id: str
    at: datetime
    mode: str
    version: int
    choices: int
    seed: int
    role: str
    answer: str  # the first answer in words: "9", "the duck", "an arrangement"
    correct: bool
    counted: bool
    why: str  # why it did not count; empty when it did
    struck: bool
    tries: int
    outcome: str


def describe(e: Event) -> str:
    """The first answer in words, from the rebuilt round; the bare id when its template version is no longer kept."""
    option = e.first_answer.get("option")
    if not isinstance(option, str):
        return "an arrangement"
    try:
        r = rounds.generate(Mode(e.mode), e.choices, e.seed, e.version)
    except ValueError:
        return option
    return next((o.word for o in r.options if o.id == option), option)


def evidence_rows(events: Iterable[Event], skill: str, titles: Mapping[str, str]) -> list[EvidenceRow]:
    """The attempts that touched `skill`, newest first."""
    rows = [
        EvidenceRow(
            event_id=u.event.event_id,
            at=u.event.presented_at,
            mode=u.event.mode,
            version=u.event.version,
            choices=u.event.choices,
            seed=u.event.seed,
            role=u.role,
            answer=describe(u.event),
            correct=u.event.first_correct,
            counted=u.counted,
            why=u.why,
            struck=u.event.struck is not None,
            tries=u.event.tries,
            outcome=u.event.outcome,
        )
        for u in uses(events, titles).get(skill, [])
    ]
    return rows[::-1]


def differences(saved: Sequence[SkillReport], rebuilt: Sequence[SkillReport]) -> list[str]:
    """Where a rebuilt report differs from a saved one, as sentences; empty when they agree exactly."""
    a = {r.skill: r for r in saved}
    b = {r.skill: r for r in rebuilt}
    out = [f"{k}: only in the saved report" for k in sorted(a.keys() - b.keys())]
    out += [f"{k}: only in the rebuilt report" for k in sorted(b.keys() - a.keys())]
    for k in sorted(a.keys() & b.keys()):
        x, y = a[k].model_dump(mode="json"), b[k].model_dump(mode="json")
        out += [f"{k}: {f} was {x[f]!r}, rebuilt {y[f]!r}" for f in x if x[f] != y[f]]
    return out
