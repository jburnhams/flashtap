"""Engagement (src/flashtap/learners/engagement.py): preferences from ratings and picks, the per-kind rows, and the
patterns named as hypotheses (spec §11). Synthetic logs; learners are invented."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from flashtap.learners.engagement import SHRINK, Offered, Pick, Rated, as_of_ratings, preferences, report
from flashtap.learners.evidence import Event

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
TITLES = {"counting": "Counting", "listen": "Listen", "give": "Give a number"}


def event(
    mode: str = "counting",
    *,
    right: bool = True,
    secs: float = 2.0,
    tries: int = 1,
    session: str = "s1",
    n: int = 0,
    outcome: str = "right",
) -> Event:
    at = T0 + timedelta(minutes=n)
    return Event(
        event_id=uuid.uuid4().hex,
        session_id=session,
        mode=mode,
        version=1,
        choices=4,
        seed=n,
        mechanic="select_one",
        options=4,
        skills=[],
        asked="next",
        presented_at=at,
        answered_at=at + timedelta(seconds=secs),
        first_answer={},
        first_correct=right,
        tries=tries,
        outcome=outcome,
    )


def rated(mode: str, value: int, n: int = 0) -> Rated:
    return Rated(event_id=uuid.uuid4().hex, session_id="s1", mode=mode, value=value, at=T0 + timedelta(minutes=n))


def test_preferences_shrink_towards_nothing_and_stay_within_one() -> None:
    assert preferences([], []) == {}
    assert preferences([rated("counting", 1)], []) == {"counting": pytest.approx(1 / (1 + SHRINK))}
    many = preferences([rated("counting", 1, i) for i in range(40)], [])
    assert 0.9 < many["counting"] <= 1.0
    pick = Pick(picked="listen", passed="give", at=T0)
    assert preferences([], [pick]) == {
        "give": pytest.approx(-0.5 / (1 + SHRINK)),
        "listen": pytest.approx(0.5 / (1 + SHRINK)),
    }
    assert as_of_ratings([rated("counting", 1, 5)], T0) == []


def test_an_offer_is_a_pick_only_once_picked() -> None:
    assert Offered(first="listen", second="give").pick() is None
    assert Offered(first="listen", second="give", picked="give", at=T0).pick() == Pick(
        picked="give", passed="listen", at=T0
    )


def test_each_kind_has_its_row() -> None:
    log = [event(n=0), event(right=False, tries=3, secs=8, n=1), event("listen", n=2, outcome="left", right=False)]
    struck = event("give", n=3).model_copy(update={"struck": "not them"})
    offers = [
        Offered(first="counting", second="give", picked="counting", at=T0),
        Offered(first="listen", second="give"),
    ]
    out = report([*log, struck], [rated("counting", 1), rated("counting", -1), rated("listen", 0)], offers, TITLES)
    rows = {k.mode: k for k in out.kinds}
    assert [k.title for k in out.kinds] == ["Counting", "Give a number", "Listen"]
    c = rows["counting"]
    assert (c.rounds, c.right_first, c.median_seconds, c.mean_tries, c.left) == (2, 1, 5.0, 2.0, 0)
    assert (c.liked, c.okay, c.disliked, c.offered, c.picked) == (1, 0, 1, 1, 1)
    assert c.preference == pytest.approx(round(0.5 / (3 + SHRINK), 3))
    g = rows["give"]  # struck rounds count for nothing; offered twice, passed over once
    assert (g.rounds, g.median_seconds, g.mean_tries, g.offered, g.picked) == (0, None, None, 2, 0)
    assert g.preference < 0
    assert rows["listen"].left == 1
    assert out.hypotheses == []  # too few rounds to name a pattern


def test_quick_and_right_and_stuck_are_named_with_what_could_explain_them() -> None:
    quick = [event(n=i, secs=1.5) for i in range(6)]
    stuck = [event("listen", right=i == 0, tries=3, secs=20, n=10 + i) for i in range(6)]
    out = report([*quick, *stuck], [], [], TITLES)
    by = {h.code: h for h in out.hypotheses}
    assert by["quick_and_right"].mode == "counting"
    assert by["quick_and_right"].seen == "Counting: right first time in 100% of the last 6, answered quickly."
    assert by["stuck"].mode == "listen"
    assert "17%" in by["stuck"].seen
    assert by["stuck"].could_be.startswith("Stuck on the skill, unsure what the round asks")
    slow_but_right = report([event(n=i, secs=30) for i in range(6)], [], [], TITLES)
    assert slow_but_right.hypotheses == []  # slowness alone is never a pattern


def test_sad_faces_and_passing_over_are_named() -> None:
    faces = [rated("listen", -1, 0), rated("listen", -1, 1), rated("listen", 1, 2)]
    offers = [Offered(first="give", second="counting", picked="counting", at=T0) for _ in range(4)]
    out = report([], faces, offers, TITLES)
    assert [(h.code, h.mode) for h in out.hypotheses] == [("passed_over", "give"), ("disliked", "listen")]
    assert out.hypotheses[1].seen == "Listen: rated with the sad face 2 of 3 times."


def test_fewer_right_late_in_long_sessions_is_named_once() -> None:
    def session(sid: str) -> list[Event]:
        return [event(session=sid, n=i, right=i < 5, secs=5) for i in range(10)]

    out = report([*session("a"), *session("b")], [], [], {})
    (late,) = [h for h in out.hypotheses if h.code == "late_decline"]
    assert late.mode is None
    assert late.seen == "Over 2 longer sessions, 100% right first time in the first half, 0% in the second."
    assert [h.code for h in report(session("a"), [], [], {}).hypotheses if h.code == "late_decline"] == []
    even = [event(session=s, n=i, right=i % 2 == 0, secs=5) for s in "ab" for i in range(10)]
    assert [h.code for h in report(even, [], [], {}).hypotheses] == []
