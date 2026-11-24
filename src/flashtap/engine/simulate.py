"""Simulated learners (spec §16, "synthetic learner simulation"): the plan's exit test for the adaptive engine, run
before any real child has played, and a way to see what a change to the engine does.

A simulated learner has a hidden set of skills it knows. Its start follows the skill graph: a skill can be known only
when its strong prerequisites are, and deeper skills are less likely, more so for a learner of lower ability `theta`
(drawn per learner; nothing here is an age). It answers a round right with chance 1 - slip when it knows every skill
the round names, less `STEP_COST` for each step of difficulty above the easiest (a bigger number range or more to
choose from trips up even a learner who knows the skill), else with the round's chance of a lucky answer. After a round it may learn the round's primary skill,
if it knows that skill's prerequisites, at its own learning rate; between sessions it forgets a little.

`run` plays each learner through `sessions` sessions chosen by a policy (the engine's, or uniform at random for
comparison), one to three days apart, logging events exactly as the server would. `report` then splits the learners,
fits every predictor on the first 70% and scores them on the rest, and says how many skills the learners came to know
under each policy. Everything is drawn from one seed, so a report is reproducible.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from flashtap import rounds
from flashtap.engine.evaluate import Fitted, Score, fit, scores
from flashtap.engine.model import SHAPE, SHAPES, Graph, Knowledge, graph, guess
from flashtap.engine.policy import POLICY, Action, Config, Past, Policy, decide
from flashtap.learners.evidence import Event, SkillUse
from flashtap.mechanics import SEED_LIMIT, Mode

START = datetime(2026, 1, 5, 16, 0, tzinfo=UTC)
STEP_COST = 0.06  # the share of right answers a knowing learner loses per step of difficulty
CONFIG = Config(choices=4, tries=0)


@dataclass
class Sim:
    id: str
    theta: float
    known: set[str]
    learn: float
    slip: float
    rng: random.Random = field(repr=False)


def learner(i: int, g: Graph, rng: random.Random) -> Sim:
    theta = rng.gauss(0, 1)
    known: set[str] = set()
    for s in sorted(g.skills, key=lambda s: (g.depth(s), s)):
        chance = 1 / (1 + math.exp(-(1.5 * theta + 1.0 - 1.0 * g.depth(s))))
        if g.before[s] <= known and rng.random() < chance:
            known.add(s)
    return Sim(
        id=f"sim{i:04d}",
        theta=theta,
        known=known,
        learn=min(0.5, 0.18 * math.exp(0.4 * theta)),
        slip=rng.uniform(0.03, 0.12),
        rng=random.Random(rng.getrandbits(64)),
    )


def _uniform(key: str) -> tuple[Mode, int]:
    rng = random.Random(key)
    return rng.choice(SHAPES).mode, rng.randrange(SEED_LIMIT)


def play(sim: Sim, g: Graph, sessions: int, policy: Policy | None) -> list[Event]:
    """One learner's whole log under `policy` (None: a kind of round uniformly at random, as Mixed plays)."""
    rng = sim.rng
    k = Knowledge(g)
    log: list[Event] = []
    day = START
    for n in range(sessions):
        sid = f"{sim.id}-s{n}"
        now = day + timedelta(minutes=rng.randrange(0, 120))
        past = Past(started=now)
        decisions: list[tuple[Action, Mode | None]] = []
        answers: list[tuple[Mode, bool]] = []
        seq = -1
        while True:  # the policy ends every session: at most max_rounds rounds, never two breaks running
            seq += 1
            past = Past(started=past.started, decisions=list(decisions), answers=list(answers))
            if policy is not None:
                c = decide(k, past, CONFIG, f"{sid}:{seq}", now, policy)
                action, mode, seed, level = c.action, c.mode, c.seed, c.level
            else:
                action, (mode, seed), level = Action.ROUND, _uniform(f"{sid}:{seq}"), None
                if len(past.rounds()) >= CONFIG.max_rounds:
                    action, mode = Action.END, None
            decisions.append((action, mode))
            if action is Action.END:
                break
            if action is Action.BREAK or mode is None or seed is None:
                now += timedelta(minutes=1)
                continue
            shape = SHAPE[mode]
            choices = CONFIG.choices if level is None else rounds.TEMPLATES[mode].levels[level].choices
            options = shape.options(choices)
            knowing = (1 - sim.slip) * (1 - STEP_COST * (level or 0))
            right = rng.random() < (knowing if set(shape.skills) <= sim.known else guess(options))
            e = Event(
                event_id=f"{rng.getrandbits(128):032x}",
                session_id=sid,
                mode=mode.value,
                version=shape.version,
                choices=choices,
                content=rounds.content_of(mode),
                seed=seed,
                level=level,
                mechanic=shape.mechanic.value,
                options=options,
                skills=[SkillUse(skill=s, role=r) for s, r in shape.roles],
                asked="mixed" if policy is None else "next",
                presented_at=now,
                answered_at=now + timedelta(seconds=rng.randrange(3, 15)),
                first_answer={},
                first_correct=right,
                tries=1 if right else 2,
                outcome="right",
            )
            log.append(e)
            k.observe(e)
            answers.append((mode, right))
            for skill, role in shape.roles:  # the round teaches what it asks, its primary skill most
                rate = sim.learn if role == "primary" else sim.learn / 2
                if skill not in sim.known and g.before[skill] <= sim.known and rng.random() < rate:
                    sim.known.add(skill)
            now += timedelta(seconds=rng.randrange(15, 40))
        gap = rng.randrange(1, 4)
        for s in sorted(sim.known):
            if rng.random() < 1 - math.exp(-0.01 * gap):
                sim.known.discard(s)
        day += timedelta(days=gap)
    return log


class Gain(BaseModel):
    policy: str
    known_before: float  # skills known at the start, mean over learners
    known_after: float


class SimReport(BaseModel):
    seed: int
    learners: int
    sessions: int
    trained_on: int
    held_out: int
    attempts: int
    fitted: str
    scores: list[Score]  # on the held-out learners, best first
    beats_rule: bool  # the engine's model predicts held-out answers better than the rule baseline
    gains: list[Gain]


def report(learners: int = 200, sessions: int = 6, seed: int = 1, g: Graph | None = None) -> SimReport:
    if learners < 4:
        raise ValueError("a simulation needs at least 4 learners, to hold some out")
    g = g or graph()
    gains: list[Gain] = []
    logs: list[list[Event]] = []
    for policy in (POLICY, None):
        rng = random.Random(seed)  # the same learners under each policy
        sims = [learner(i, g, rng) for i in range(learners)]
        before = sum(len(s.known) for s in sims) / learners
        played = [play(s, g, sessions, policy) for s in sims]
        name = "random" if policy is None else policy.id
        gains.append(
            Gain(
                policy=name,
                known_before=round(before, 3),
                known_after=round(sum(len(s.known) for s in sims) / learners, 3),
            )
        )
        if policy is not None:
            logs = played
    cut = int(learners * 0.7)
    train, held = logs[:cut], logs[cut:]
    f: Fitted = fit(train, g)
    s = scores(held, g, f)
    by = {x.model: x for x in s}
    return SimReport(
        seed=seed,
        learners=learners,
        sessions=sessions,
        trained_on=len(train),
        held_out=len(held),
        attempts=sum(len(x) for x in logs),
        fitted=f"engine {f.engine.label()}; bkt {f.bkt.label()}; rule window {f.window}",
        scores=s,
        beats_rule=by["engine"].log_loss < by["rule"].log_loss,
        gains=gains,
    )


def describe(r: SimReport) -> Sequence[str]:
    lines = [
        f"{r.learners} simulated learners, {r.sessions} sessions each, seed {r.seed}: {r.attempts} attempts",
        f"fitted on {r.trained_on} learners ({r.fitted}); scored on {r.held_out} held out:",
    ]
    lines += [f"  {s.model:<7} log loss {s.log_loss:.4f}  Brier {s.brier:.4f}  ({s.description})" for s in r.scores]
    lines += [
        f"  skills known under the {x.policy} policy: {x.known_before:.2f} before, {x.known_after:.2f} after"
        for x in r.gains
    ]
    lines.append(
        "the engine's model beats the rule baseline"
        if r.beats_rule
        else "the engine's model does NOT beat the rule baseline"
    )
    return lines
