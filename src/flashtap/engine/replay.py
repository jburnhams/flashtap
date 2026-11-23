"""Replaying the engine's logged decisions (spec §14: "record generator seed, source versions and policy selection
probabilities for offline replay"; §15 `POST /v1/evaluations/replay`).

Each decision is made again from what the server knew when it made it: the attempts received by then (struck or not as
they stood then), the session's earlier decisions, its start and settings, the same key for the draw and the same
time. The engine is a pure function of those, so a decision that comes out different means the log, the policy or the
code under it changed, and the replay says which decision and how. Only the current policy is kept, as only the current
version of each round template is: a decision made by another is reported, not remade.
"""

from collections.abc import Sequence
from datetime import datetime

from flashtap.engine.model import Graph, Params, fold
from flashtap.engine.policy import POLICY, Choice, Config, Logged, Past, decide
from flashtap.learners.evidence import Event, ordered
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
            (d.action, d.mode)
            for d in sorted(decisions, key=lambda d: d.seq)
            if d.session_id == session and d.seq < seq
        ],
        answers=[
            (Mode(e.mode), e.first_correct)
            for e in ordered(as_of(events, at))
            if e.session_id == session and e.struck is None
        ],
    )


def remake(
    d: Logged, events: Sequence[Event], decisions: Sequence[Logged], started: datetime, config: Config, g: Graph
) -> Choice:
    k = fold(as_of(events, d.at), g, Params())
    past = past_of(started, decisions, events, d.session_id, d.at, d.seq)
    return decide(k, past, config, f"{d.session_id}:{d.seq}", d.at)


def _fields(c: Choice) -> dict[str, object]:
    return Choice.model_validate(c.model_dump(include=set(Choice.model_fields))).model_dump(mode="json")


def replay(
    events: Sequence[Event],
    decisions: Sequence[Logged],
    sessions: dict[str, tuple[datetime, Config | None]],
    g: Graph,
) -> tuple[int, list[str]]:
    """Remake every decision; return how many came out identical and a sentence for each that did not."""
    same, out = 0, list[str]()
    for d in sorted(decisions, key=lambda d: (d.at, d.session_id, d.seq)):
        where = f"decision {d.seq} of session {d.session_id}"
        if d.policy != POLICY.id:
            out.append(f"{where}: made by {d.policy}, which is not kept (now {POLICY.id})")
            continue
        started, config = sessions.get(d.session_id, (None, None))
        if started is None or config is None:
            out.append(f"{where}: its session's start and settings are not in the log")
            continue
        a, b = _fields(d), _fields(remake(d, events, decisions, started, config, g))
        diff = [k for k in a if a[k] != b[k]]
        if diff:
            parts = [f"{k} was {a[k]!r}, remade {b[k]!r}" for k in diff if k != "candidates"]
            out.append(f"{where}: " + "; ".join([*parts, *(["the candidates differ"] if "candidates" in diff else [])]))
        else:
            same += 1
    return same, out
