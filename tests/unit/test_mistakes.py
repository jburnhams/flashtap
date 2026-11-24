"""Mistakes read as misconceptions and answer speed read as fluency (0.12.0): `mistakes.py` (which wrong option shows
which misconception), `learners/misconceptions.py` (the tally, its chance and its status), `learners/fluency.py`, how
both reach the Learner report, and the engine's checks of a suspected misconception (policy utility@5), on a real
migrated database where it matters. Learners are invented ("Fox")."""

import functools
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from flashtap import content, mistakes, rounds
from flashtap import distractors as dx
from flashtap.engine import model, policy, sessions
from flashtap.engine.model import Knowledge, fold
from flashtap.engine.policy import Action, Config, Past, Why, decide, explain
from flashtap.learners import misconceptions, store
from flashtap.learners.evidence import Event, SkillUse, uses
from flashtap.learners.fluency import AWAY, FRESH, fluency, starts, timed
from flashtap.learners.misconceptions import MisconceptionStatus as Status
from flashtap.learners.misconceptions import Tally, observe, tail, tallies
from flashtap.learners.report import DISTRACTOR_WORDS, SkillInfo, State, evidence_rows, mistake, skill_reports
from flashtap.mechanics import Mode, Option, Round

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
G = model.graph()
NUMERAL = "maths.numerals.recognise"
COUNT = "maths.counting.objects"
SIX_NINE = mistakes.REVERSAL_6_9


def find(mode: Mode, level: int, test: Callable[[Round], bool], tries: int = 2000) -> Round:
    """The first round of `mode` at `level` for which `test(round)` holds."""
    for seed in range(tries):
        r = rounds.at_level(mode, level, seed)
        if test(r):
            return r
    raise AssertionError(f"no {mode} round at step {level} in {tries} seeds")


def six_for_nine(r: Round) -> bool:
    return r.answer == "n6" and any(o.id == "n9" for o in r.options)


# Which option shows which misconception


def test_every_misconception_named_is_in_the_packs() -> None:
    known = content.load().misconceptions
    assert set(mistakes.NAMED) <= set(known)
    assert set(mistakes.PROBES) == set(mistakes.NAMED)


def test_nine_for_six_shows_the_reversal_and_a_near_count_a_counting_slip() -> None:
    r = find(Mode.COUNTING, 3, six_for_nine)
    t = mistakes.traps(r)
    assert "n9" in t[SIX_NINE]
    nine = next(o for o in r.options if o.id == "n9")
    assert mistakes.shows(r, nine) == SIX_NINE
    assert mistakes.shows(r, next(o for o in r.options if o.correct)) is None
    for o in r.options:  # a near number in Counting reads as a slip of counting only within two
        if o.id in t.get(mistakes.ONE_TO_ONE, []):
            assert o.distractor == dx.NEAR_NUMBER
            assert abs(int(o.word) - 6) <= mistakes.COUNT_SLIP


def test_a_near_number_three_out_or_in_another_kind_shows_nothing() -> None:
    r = find(Mode.COUNTING, 3, lambda r: r.answer == "n1")
    far = r.model_copy(
        update={
            "options": [
                *(o for o in r.options if o.correct),
                Option(id="n4", picture="4", word="4", correct=False, feedback="", distractor=dx.NEAR_NUMBER),
            ]
        }
    )
    four = far.options[-1]
    assert mistakes.shows(far, four) is None
    missing = rounds.at_level(Mode.MISSING, 1, 3)
    assert all(mistakes.shows(missing, o) != mistakes.ONE_TO_ONE for o in missing.options)


def test_two_digits_turned_round_show_the_teen_reversal() -> None:
    r = rounds.at_level(Mode.MISSING, 3, 1)
    right = Option(id="n12", picture="12", word="12", correct=True, feedback="", distractor="")
    flip = Option(id="n21", picture="21", word="21", correct=False, feedback="", distractor=dx.REVERSAL)
    teen = r.model_copy(update={"options": [right, flip], "answer": "n12"})
    assert mistakes.traps(teen) == {mistakes.TEEN_REVERSAL: ["n21"]}


def test_mirror_letters_only_among_b_d_p_and_q() -> None:
    r = find(Mode.LISTEN, 0, lambda r: mistakes.MIRROR_LETTERS in mistakes.traps(r))
    ids = mistakes.traps(r)[mistakes.MIRROR_LETTERS]
    assert all(next(o for o in r.options if o.id == i).word in mistakes.MIRROR for i in ids)
    pictures = find(Mode.LETTERS, 0, lambda r: mistakes.MIRROR_LETTERS in mistakes.traps(r))
    assert pictures.show.lower() in mistakes.MIRROR  # Letters reads the picture's first letter
    m = Option(id="l_m", picture="m", word="m", correct=True, feedback="", distractor="")
    w = Option(id="l_w", picture="w", word="w", correct=False, feedback="", distractor=dx.CONFUSABLE_GRAPHEME)
    assert mistakes.traps(r.model_copy(update={"options": [m, w], "answer": "l_m"})) == {}


def test_a_placing_round_shows_none() -> None:
    assert mistakes.traps(rounds.at_level(Mode.CAPITALS, 0, 1)) == {}


@pytest.mark.parametrize(
    ("misconception", "mode", "level"), [(m, k, lv) for m, ks in mistakes.PROBES.items() for k, lv in ks.items()]
)
def test_each_probe_kind_offers_its_trap_within_the_tries_and_not_below_its_step(
    misconception: str, mode: Mode, level: int
) -> None:
    steps = len(rounds.TEMPLATES[mode].levels)
    for lv in range(level, steps):
        find(mode, lv, lambda r: misconception in mistakes.traps(r), policy.PROBE_TRIES)
    for lv in range(level):
        assert not any(misconception in mistakes.traps(rounds.at_level(mode, lv, s)) for s in range(500))


# The tally


def ev(
    *,
    right: bool,
    tapped: str | None = None,
    traps: dict[str, list[str]] | None = None,
    at: datetime = T0,
    seconds: float = 3.0,
    mode: Mode = Mode.COUNTING,
    level: int | None = 2,
    session: str = "s1",
    struck: str | None = None,
    role: str = "primary",
    skill: str = COUNT,
    options: int = 4,
) -> Event:
    return Event(
        event_id=uuid.uuid4().hex,
        session_id=session,
        mode=mode.value,
        version=1,
        choices=options,
        seed=1,
        level=level,
        mechanic=model.SHAPE[mode].mechanic.value,
        options=options,
        skills=[SkillUse(skill=skill, role=role)],
        asked="next",
        presented_at=at,
        answered_at=at + timedelta(seconds=seconds),
        first_answer={"option": "right" if right else tapped or "other"},
        first_correct=right,
        tries=1 if right else 2,
        outcome="right",
        struck=struck,
        distractor="" if right else dx.REVERSAL if tapped == "n9" else dx.RANDOM,
        traps={SIX_NINE: ["n9"]} if traps is None else traps,
    )


def test_the_chance_of_so_many_by_luck_is_a_poisson_binomial_tail() -> None:
    assert tail([0.5, 0.5], 2) == pytest.approx(0.25)
    assert tail([0.5, 0.5], 1) == pytest.approx(0.75)
    assert tail([], 0) == 1.0
    assert tail([0.2], 2) == 0.0


def test_a_misconception_is_unseen_then_unclear_then_suspected_then_cleared() -> None:
    t: dict[str, Tally] = {}
    observe(t, ev(right=False, tapped="other"))
    assert t[SIX_NINE].status is Status.NOT_SEEN
    assert t[SIX_NINE].wrong == 1
    observe(t, ev(right=False, tapped="n9", at=T0 + timedelta(minutes=1)))
    assert t[SIX_NINE].status is Status.UNCLEAR
    assert t[SIX_NINE].open
    observe(t, ev(right=False, tapped="n9", at=T0 + timedelta(minutes=2)))
    observe(t, ev(right=False, tapped="n9", at=T0 + timedelta(minutes=3)))
    assert t[SIX_NINE].status is Status.UNCLEAR  # 3 of 4 where luck gives one in three: 1 in 9 by luck, not enough
    observe(t, ev(right=False, tapped="n9", at=T0 + timedelta(minutes=3, seconds=30)))
    x = t[SIX_NINE]
    assert (x.offered, x.wrong, x.shown, x.expected) == (5, 5, 4, pytest.approx(5 / 3))
    assert x.status is Status.SUSPECTED  # 4 of 5: under 1 in 20 by luck
    observe(t, ev(right=True, at=T0 + timedelta(minutes=4)))
    observe(t, ev(right=False, tapped="other", at=T0 + timedelta(minutes=5)))  # a wrong tap elsewhere breaks the run
    assert x.right_since == 0
    for i in range(misconceptions.CLEAR):
        observe(t, ev(right=True, at=T0 + timedelta(minutes=6 + i)))
    assert x.status is Status.CLEARED
    assert not x.open
    assert x.last_shown == T0 + timedelta(minutes=3, seconds=30)
    assert x.skills == {COUNT}


def test_struck_rounds_and_older_attempts_count_for_nothing() -> None:
    old = ev(right=False, tapped="n9").model_copy(update={"traps": None})
    assert tallies([old, ev(right=False, tapped="n9", struck="someone else")]) == {}


def test_the_report_names_each_one_offered_suspected_first() -> None:
    log = [ev(right=False, tapped="n9", at=T0 + timedelta(minutes=i)) for i in range(3)]
    log.append(ev(right=True, traps={"maths.misconception.gone": ["x"]}, at=T0 + timedelta(minutes=9)))
    out = misconceptions.report(log, content.load().misconceptions)
    assert [r.id for r in out] == [SIX_NINE, "maths.misconception.gone"]
    six = out[0]
    assert (six.status, six.shown, six.title) == (Status.SUSPECTED, 3, "Confuses 6 and 9")
    assert six.skills == [NUMERAL, COUNT]  # the packs' skill, then the round's
    assert six.checks
    assert out[1].title == "maths.misconception.gone"
    assert not out[1].checks
    assert out[1].status is Status.NOT_SEEN
    assert misconceptions.suspected(out) == {NUMERAL: ["Confuses 6 and 9"], COUNT: ["Confuses 6 and 9"]}


# Fluency


def test_only_fresh_unpaused_right_first_answers_on_the_assessed_skill_are_timed() -> None:
    log = [
        ev(right=True, at=T0),
        ev(right=False, at=T0 + timedelta(minutes=1)),
        ev(right=True, role="secondary", at=T0 + timedelta(minutes=2)),
        ev(right=True, struck="someone else", at=T0 + timedelta(minutes=3)),
        ev(right=True, seconds=AWAY + 1, at=T0 + timedelta(minutes=4)),
        ev(right=True, at=T0 + FRESH + timedelta(minutes=1)),
        ev(right=True, at=T0 + timedelta(minutes=5), seconds=5),
    ]
    got = timed(uses(log)[COUNT], starts(log))
    assert [e.seconds for e in got] == [3.0, 5.0]
    f = fluency(uses(log)[COUNT], starts(log))
    assert f is not None
    assert (f.seconds, f.low, f.high, f.used, f.trend) == (4.0, 3.0, 5.0, 2, None)
    assert fluency(uses([ev(right=False)])[COUNT], {}) is None


def times(*secs: float, mode: Mode = Mode.COUNTING, level: int | None = 2, start: int = 0) -> list[Event]:
    return [
        ev(right=True, seconds=s, mode=mode, level=level, at=T0 + timedelta(minutes=start + i))
        for i, s in enumerate(secs)
    ]


@pytest.mark.parametrize(
    ("secs", "trend"),
    [
        ((8, 8, 8, 4, 4, 4), "quicker"),
        ((4, 4, 4, 8, 8, 8), "slower"),
        ((5, 6, 5, 6, 5, 6), "steady"),
        ((0, 0, 0, 5, 5, 5), "steady"),
    ],
)
def test_the_trend_compares_the_newer_half_with_the_older(secs: tuple[float, ...], trend: str) -> None:
    log = times(*secs)
    f = fluency(uses(log)[COUNT], starts(log))
    assert f is not None
    assert f.trend == trend
    assert f.used == 6
    assert f.low <= f.seconds <= f.high


def test_a_slower_kind_of_round_is_not_read_as_slowing_down() -> None:
    """Quick look's answers include the moment its pictures show: newer rounds of it are slower, yet within each kind
    the learner is as quick as ever."""
    log = [*times(3, 3, 3, mode=Mode.COUNTING), *times(9, 9, 9, mode=Mode.QUICK_LOOK, start=3)]
    log += [ev(right=True, seconds=0, level=None, at=T0 + timedelta(minutes=8))]  # a group whose median is 0
    f = fluency(uses(log)[COUNT], starts(log))
    assert f is not None
    assert f.trend == "steady"


# The Learner report


def test_a_suspected_misconception_holds_its_skills_at_emerging_and_moves_no_estimate() -> None:
    skills = [SkillInfo(id=NUMERAL, title="Read a numeral", domain="Maths", strand="Numerals")]
    rights = [
        ev(right=True, skill=NUMERAL, traps={}, mode=Mode.MISSING, at=T0 + timedelta(minutes=i)) for i in range(5)
    ]
    rights += [
        ev(right=True, skill=NUMERAL, traps={}, mode=Mode.COUNTING, at=T0 + timedelta(minutes=5 + i)) for i in range(5)
    ]
    clean = skill_reports(rights, skills)[0]
    assert clean.state is State.INDEPENDENT  # the top it can reach: reading numerals has no transfer kind of its own
    assert clean.suspected == []
    assert clean.fluency is not None
    slips = [ev(right=False, tapped="n9", skill=COUNT, at=T0 - timedelta(minutes=10 - i)) for i in range(3)]
    held = skill_reports([*slips, *rights], skills)[0]
    assert held.state is State.EMERGING
    assert held.suspected == ["Confuses 6 and 9"]
    assert held.estimates == clean.estimates  # the slips were on Counting's skill: NUMERAL's evidence is the same


def test_a_wrong_answer_is_said_in_words() -> None:
    named = {SIX_NINE: "Confuses 6 and 9"}
    assert mistake(ev(right=True), named) == ""
    assert mistake(ev(right=False, tapped="n9"), named) == "Confuses 6 and 9"
    assert mistake(ev(right=False, tapped="other"), named) == ""  # a random one says nothing
    near = ev(right=False, tapped="n5").model_copy(update={"distractor": dx.NEAR_NUMBER})
    assert mistake(near, named) == DISTRACTOR_WORDS[dx.NEAR_NUMBER]
    assert mistake(near.model_copy(update={"distractor": None}), named) == ""


# Recorded on a real database


@pytest.fixture
def fox(db_session: Session) -> str:
    return store.add_learner(db_session, "Fox", at=T0).id


def tap(
    db: Session,
    learner: str,
    r: Round,
    option: str,
    at: datetime,
    decision: str | None = None,
    session: str | None = None,
) -> store.Ack:
    right = option == r.answer
    return store.record(
        db,
        store.AttemptIn(
            event_id=uuid.uuid4().hex,
            learner_id=learner,
            session_id=session or "5e55" + learner[4:],
            mode=r.mode,
            version=r.version,
            choices=r.choices,
            seed=r.seed,
            level=r.level,
            asked="next" if decision else Mode.MIXED,
            presented_at=at,
            answered_at=at + timedelta(seconds=4),
            first_answer=store.FirstAnswer(option=option),
            tries=1 if right else 2,
            outcome="right",
            decision_id=decision,
        ),
        at=at + timedelta(seconds=5),
    )


def test_an_attempt_stores_what_its_first_answer_showed_and_the_evidence_says_it(db_session: Session, fox: str) -> None:
    r = find(Mode.COUNTING, 3, six_for_nine)
    tap(db_session, fox, r, "n9", T0)
    (e,) = store.events(db_session, fox)
    assert e.distractor == dx.REVERSAL
    assert e.traps == mistakes.traps(r)
    assert e.showed() == SIX_NINE
    (row,) = evidence_rows([e], COUNT, {})
    assert (row.mistake, row.seconds) == ("Confuses 6 and 9", 4.0)
    p = store.profile(db_session, fox, [SkillInfo(id=COUNT, title="Count", domain="Maths", strand="Counting")])
    assert [m.id for m in p.misconceptions] == [SIX_NINE, mistakes.ONE_TO_ONE]
    assert p.misconceptions[0].status is Status.UNCLEAR
    out = store.export(db_session, fox, [SkillInfo(id=COUNT, title="Count", domain="Maths", strand="Counting")])
    assert out.events[0].traps == e.traps
    assert store.rebuild(store.Export.model_validate_json(out.model_dump_json())) == []


# The engine (utility@5)


def suspicious(*more: Event) -> Knowledge:
    return fold([*(ev(right=False, tapped="n9", at=T0 - timedelta(hours=1, minutes=i)) for i in range(3)), *more], G)


def counting(c: policy.Choice) -> policy.Candidate:
    return next(x for x in c.candidates if x.mode is Mode.COUNTING)


def test_a_suspected_misconception_gives_rounds_that_can_offer_its_trap_a_bonus() -> None:
    k = suspicious()
    assert k.mistakes[SIX_NINE].status is Status.SUSPECTED
    k.stairs[Mode.COUNTING] = model.Stair(level=3, last=3)
    c = decide(k, Past(started=T0), Config(choices=4, tries=0), "s:0", T0)
    x = counting(c)
    assert (x.probe, x.misconception) == (SIX_NINE, 1.0)
    missing = next(y for y in c.candidates if y.mode is Mode.MISSING)
    assert missing.probe is None  # Missing number starts at its easiest step: numbers to 5, no 6 or 9
    k.stairs[Mode.COUNTING] = model.Stair(level=0, last=0)
    assert counting(decide(k, Past(started=T0), Config(choices=4, tries=0), "s:0", T0)).probe is None
    old = decide(suspicious(), Past(started=T0), Config(choices=4, tries=0), "s:0", T0, policy.kept("utility@4"))
    assert all(y.probe is None and y.misconception == 0 for y in old.candidates)


def test_an_unclear_one_gets_half_and_the_suspected_comes_first() -> None:
    k = fold([ev(right=False, tapped="n9", at=T0 - timedelta(hours=1))], G)
    k.stairs[Mode.COUNTING] = model.Stair(level=3, last=3)
    assert k.mistakes[SIX_NINE].status is Status.UNCLEAR
    x = counting(decide(k, Past(started=T0), Config(choices=4, tries=0), "s:0", T0))
    assert (x.probe, x.misconception) == (SIX_NINE, 0.5)
    slip = {mistakes.ONE_TO_ONE: ["n5"], SIX_NINE: ["n9"]}
    k = fold([ev(right=False, tapped="n5", traps=slip, at=T0 - timedelta(hours=1))], G)
    assert k.mistakes[mistakes.ONE_TO_ONE].status is Status.UNCLEAR
    k.mistakes[SIX_NINE] = suspicious().mistakes[SIX_NINE]
    k.stairs[Mode.COUNTING] = model.Stair(level=3, last=3)
    assert counting(decide(k, Past(started=T0), Config(choices=4, tries=0), "s:0", T0)).probe == SIX_NINE


def probed(k: Knowledge, config: Config | None = None) -> policy.Choice:
    for i in range(400):
        c = decide(k, Past(started=T0), config or Config(choices=4, tries=0), f"s:{i}", T0)
        if c.action is Action.ROUND and c.mode is Mode.COUNTING:
            return c
        if c.offers and c.offers[0].mode is Mode.COUNTING:
            return c
    raise AssertionError("Counting never picked")


def test_a_round_picked_to_check_one_offers_its_trap_and_says_so() -> None:
    k = suspicious()
    k.stairs[Mode.COUNTING] = model.Stair(level=3, last=3)
    c = probed(k)
    assert c.probe == SIX_NINE
    assert Why.PROBE in c.rationale
    assert c.level is not None
    assert c.seed is not None
    assert SIX_NINE in mistakes.traps(rounds.at_level(Mode.COUNTING, c.level, c.seed))
    assert "confuses 6 and 9" in explain(c, {}, Config(choices=4, tries=0), 0)
    chosen = probed(k, Config(choices=4, tries=0, choice_every=1))
    assert chosen.offers is not None
    assert chosen.offers[0].probe == SIX_NINE
    assert Why.PROBE in chosen.offers[0].rationale


def test_with_no_seed_offering_the_trap_the_round_is_played_without_a_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "PROBE_TRIES", 0)
    k = suspicious()
    k.stairs[Mode.COUNTING] = model.Stair(level=3, last=3)
    c = probed(k)
    assert c.probe is None
    assert Why.PROBE not in c.rationale
    assert counting(c).probe == SIX_NINE  # the candidate still says what it was weighed for
    unknown = c.model_copy(update={"probe": "maths.misconception.gone", "rationale": [Why.PROBE]})
    assert "maths.misconception.gone" in explain(unknown, {}, Config(choices=4, tries=0), 0)


def play(db: Session, learner: str, start: datetime, chooser: policy.Policy | None = None) -> int:
    """A session that taps a b, d, p or q for another whenever one is offered: returns the decisions that probed."""
    info = sessions.start(db, learner, Config(choices=4, tries=0, max_rounds=12, break_every=0), at=start)
    at, probes = start, 0
    for seq in range(40):
        n = sessions.next_decision(db, info.id, seq, G, {}, at=at)
        if n.action is Action.END:
            break
        r = n.round
        if n.action is Action.ROUND and r is not None:
            probes += Why.PROBE in n.rationale
            t = mistakes.traps(r)
            if r.places:
                store.record(
                    db,
                    store.AttemptIn(
                        event_id=uuid.uuid4().hex,
                        learner_id=learner,
                        session_id=info.id,
                        mode=r.mode,
                        version=r.version,
                        choices=r.choices,
                        seed=r.seed,
                        level=r.level,
                        asked="next",
                        presented_at=at,
                        answered_at=at + timedelta(seconds=3),
                        first_answer=store.FirstAnswer(placement={}),
                        tries=2,
                        outcome="right",
                        decision_id=n.id,
                    ),
                    at=at + timedelta(seconds=4),
                )
            else:
                tap(
                    db,
                    learner,
                    r,
                    t[mistakes.MIRROR_LETTERS][0] if mistakes.MIRROR_LETTERS in t else r.answer,
                    at,
                    n.id,
                    info.id,
                )
        at += timedelta(seconds=30)
    return probes


def test_sessions_that_probe_replay_exactly_and_utility_4_ignores_the_tally(
    db_session: Session, fox: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Three mirror-letter taps first, so the misconception is open before the engine's first session.
    for n in range(3):
        r = find(
            Mode.LISTEN, 0, lambda r, after=n * 100: mistakes.MIRROR_LETTERS in mistakes.traps(r) and r.seed > after
        )
        tap(db_session, fox, r, mistakes.traps(r)[mistakes.MIRROR_LETTERS][0], T0 - timedelta(hours=1, minutes=n))
    probes = sum(play(db_session, fox, T0 + timedelta(hours=h)) for h in range(4))
    assert probes > 0
    assert any(d.probe == mistakes.MIRROR_LETTERS for d in store.decisions(db_session, fox))
    out = sessions.evaluate(db_session, sessions.ReplayIn(learner_id=fox), G)
    assert (out.reproduced, out.differences) == (out.decisions, [])
    monkeypatch.setattr(sessions, "decide", functools.partial(policy.decide, policy=policy.kept("utility@4")))
    assert play(db_session, fox, T0 + timedelta(days=1)) == 0
    monkeypatch.undo()
    out = sessions.evaluate(db_session, sessions.ReplayIn(learner_id=fox), G)
    assert (out.reproduced, out.differences) == (out.decisions, [])
