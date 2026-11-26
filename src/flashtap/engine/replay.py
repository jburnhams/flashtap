"""Replaying the engine's logged decisions (spec §14: "record generator seed, source versions and policy selection
probabilities for offline replay"; §15 `POST /v1/evaluations/replay`).

Each decision is made again from what the server knew when it made it: the attempts received by then (struck or not as
they stood then), the session's earlier decisions, its start and settings, the same key for the draw and the same
time. The engine is a pure function of those, so a decision that comes out different means the log, the policy or the
code under it changed, and the replay says which decision and how. Only the current policy is kept, as only the current
version of each round template and content pack is: a decision made by another policy, or for a round drawn from packs
since changed (its `content`, the versions its attempt records too), is reported, not remade: the round it served
can no longer be rebuilt, and a difference would come from the packs, not the log. A change to a skill pack the round
does not draw from still shows as a difference in the candidates.

What else the decision could see is rebuilt the same way: the grown-ups' overrides standing then
(`evidence.told_as_of`), and the learner's preferences from the ratings received and the choices picked by then
(`likes_as_of`). A pick is refused once a later decision in its session exists (sessions.pick), so the pick a replay
sees is the one the next decision saw. Older policies' decisions (`utility@1`, `@2`) are remade by the current code
over the kinds of round their version weighed (policy.OFFERS); it decides as 1 did when there are no choices, ratings
or overrides (policy.REPLAYS). A decision before `utility@7` is remade on the skill graph without the first steps'
skills, which joined it then (`Graph.without`): their edges change the readiness and reach of the kinds they open.
`maths.number` version 2's two edges are a pack change like any other and show as differences in the candidates.
"""

from collections.abc import Sequence
from datetime import datetime

from flashtap import rounds
from flashtap.engine.model import Graph, Params, fold
from flashtap.engine.policy import (
    OPENS_FROM,
    REPLAYS,
    STARTER_SKILLS,
    Action,
    Choice,
    Config,
    Logged,
    Past,
    decide,
    kept,
)
from flashtap.learners.engagement import Pick, Rated, as_of_ratings, preferences
from flashtap.learners.evidence import Event, Told, ordered, told_as_of
from flashtap.mechanics import Mode


def received(e: Event) -> datetime:
    return e.received_at or e.answered_at  # an export from before 0.6.0 has no receipt time


def as_of(events: Sequence[Event], at: datetime) -> list[Event]:
    """The log as the server had it at `at`: attempts received by then, struck only if struck by then."""
    out: list[Event] = []
    for e in events:
        if received(e) > at:
            continue
        if e.struck is not None and e.struck_at is not None and e.struck_at > at:
            e = e.model_copy(update={"struck": None, "struck_at": None})
        out.append(e)
    return out


def past_of(
    started: datetime, decisions: Sequence[Logged], events: Sequence[Event], session: str, at: datetime, seq: int
) -> Past:
    """Session `session` as it stood when its decision `seq` was made."""
    return Past(
        started=started,
        decisions=[
            (d.action, d.played())
            for d in sorted(decisions, key=lambda d: d.seq)
            if d.session_id == session and d.seq < seq
        ],
        answers=[
            (Mode(e.mode), e.first_correct)
            for e in ordered(as_of(events, at))
            if e.session_id == session and e.struck is None
        ],
    )


def picks(decisions: Sequence[Logged]) -> list[Pick]:
    """Every choice answered, from the logged decisions."""
    out: list[Pick] = []
    for d in decisions:
        o = d.offered(d.picked)
        if d.action is Action.CHOICE and o is not None and d.offers is not None and d.picked_at is not None:
            other = d.offers[1 - (d.picked or 0)] if len(d.offers) == 2 else o
            out.append(Pick(picked=o.mode.value, passed=other.mode.value, at=d.picked_at))
    return out


def likes_as_of(ratings: Sequence[Rated], decisions: Sequence[Logged], at: datetime) -> dict[str, float]:
    """The preferences a decision made at `at` could see: ratings received and choices picked by then."""
    return preferences(as_of_ratings(ratings, at), [p for p in picks(decisions) if p.at <= at])


def remake(
    d: Logged,
    events: Sequence[Event],
    decisions: Sequence[Logged],
    started: datetime,
    config: Config,
    g: Graph,
    ratings: Sequence[Rated] = (),
    told: Sequence[Told] = (),
) -> Choice:
    policy = kept(d.policy)
    if policy.version < OPENS_FROM:  # made before the first steps' skills joined the graph: remade without them
        g = g.without(STARTER_SKILLS)
    k = fold(as_of(events, d.at), g, Params(), told_as_of(told, d.at))
    past = past_of(started, decisions, events, d.session_id, d.at, d.seq)
    likes = likes_as_of(ratings, decisions, d.at)
    return decide(k, past, config, f"{d.session_id}:{d.seq}", d.at, policy=policy, likes=likes)


def _fields(c: Choice) -> dict[str, object]:
    return Choice.model_validate(c.model_dump(include=set(Choice.model_fields))).model_dump(mode="json")


def replay(
    events: Sequence[Event],
    decisions: Sequence[Logged],
    sessions: dict[str, tuple[datetime, Config | None]],
    g: Graph,
    ratings: Sequence[Rated] = (),
    told: Sequence[Told] = (),
) -> tuple[int, list[str]]:
    """Remake every decision; return how many came out identical and a sentence for each that did not."""
    same, out = 0, list[str]()
    for d in sorted(decisions, key=lambda d: (d.at, d.session_id, d.seq)):
        where = f"decision {d.seq} of session {d.session_id}"
        if d.policy not in REPLAYS:
            out.append(f"{where}: made by {d.policy}, which is not kept (now {', '.join(sorted(REPLAYS))})")
            continue
        drawn = [(d.mode, d.content), *((o.mode, o.content) for o in d.offers or [])]
        moved = [(c, now) for m, c in drawn if m is not None and c and c != (now := rounds.content_of(m))]
        if moved:
            made, kept = (", ".join(f"{k}@{v}" for k, v in sorted(c.items())) for c in moved[0])
            out.append(f"{where}: made from {made}, which are not kept (now {kept})")
            continue
        started, config = sessions.get(d.session_id, (None, None))
        if started is None or config is None:
            out.append(f"{where}: its session's start and settings are not in the log")
            continue
        a, b = _fields(d), _fields(remake(d, events, decisions, started, config, g, ratings, told))
        if d.content is None:
            b["content"] = None  # an export from before 0.7.0 recorded no packs (all were at 1): nothing to compare
        diff = [k for k in a if a[k] != b[k]]
        if diff:
            parts = [f"{k} was {a[k]!r}, remade {b[k]!r}" for k in diff if k != "candidates"]
            out.append(f"{where}: " + "; ".join([*parts, *(["the candidates differ"] if "candidates" in diff else [])]))
        else:
            same += 1
    return same, out
