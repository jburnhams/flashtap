"""The learner records (src/flashtap/learners/): storage on a real migrated database (the strata_python.db fixtures),
the evidence rules, the estimators, the reporting states, export and rebuild. Learners are invented ("Fox", "Owl")."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flashtap import rounds
from flashtap.learners import db as learner_db
from flashtap.learners import store
from flashtap.learners.estimators import BAYES, PLACE_GUESS, RULE
from flashtap.learners.evidence import Event, Observation, SkillUse, uses
from flashtap.learners.models import Attempt, Learner, Sitting, Tombstone, utc
from flashtap.learners.report import SkillInfo, State, differences, evidence_rows, skill_reports
from flashtap.mechanics import Mode

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
SKILLS = [
    SkillInfo(id="maths.counting.objects", title="Count objects", domain="Maths", strand="Counting"),
    SkillInfo(id="maths.numerals.recognise", title="Read a numeral", domain="Maths", strand="Numerals"),
    SkillInfo(id="maths.cardinality.last_number", title="Last number", domain="Maths", strand="Cardinality"),
    SkillInfo(id="maths.subitising.perceptual", title="See how many", domain="Maths", strand="Subitising"),
]


def attempt(
    learner: str,
    *,
    mode: Mode = Mode.COUNTING,
    seed: int = 1,
    right: bool = True,
    at: datetime = T0,
    session: str | None = None,
    event_id: str | None = None,
) -> store.AttemptIn:
    """An attempt at a real round: its right option, or its first wrong one (then right on the second tap)."""
    r = rounds.generate(mode, 4, seed)
    if r.places:
        placement = {k: s.id for s in r.places for k in s.takes[: s.holds]} if right else {}
        answer = store.FirstAnswer(placement=placement)
    else:
        answer = store.FirstAnswer(option=r.answer if right else next(o.id for o in r.options if not o.correct))
    return store.AttemptIn(
        event_id=event_id or uuid.uuid4().hex,
        learner_id=learner,
        session_id=session or "5e55" + learner[4:],
        mode=r.mode,
        version=r.version,
        choices=4,
        seed=seed,
        asked=Mode.MIXED,
        presented_at=at,
        answered_at=at + timedelta(seconds=4),
        first_answer=answer,
        tries=1 if right else 2,
        outcome="right",
    )


@pytest.fixture
def fox(db_session: Session) -> str:
    return store.add_learner(db_session, "Fox", at=T0).id


# Learners


def test_learners_are_added_listed_renamed_and_unique_by_nickname(db_session: Session) -> None:
    fox = store.add_learner(db_session, "  Fox  ", at=T0)
    assert fox.nickname == "Fox"
    assert len(fox.id) == 32
    assert fox.attempts == 0
    assert fox.last_played is None
    owl = store.add_learner(db_session, "Owl")
    assert [x.nickname for x in store.list_learners(db_session)] == ["Fox", "Owl"]
    with pytest.raises(store.Conflict, match="already a learner called Fox"):
        store.add_learner(db_session, "fox")
    with pytest.raises(store.Conflict):
        store.rename_learner(db_session, owl.id, "FOX")
    assert store.rename_learner(db_session, owl.id, "Wise   Owl").nickname == "Wise Owl"
    assert store.rename_learner(db_session, fox.id, "Fox").nickname == "Fox"  # its own name is not taken
    for bad in ("", "   ", "x" * 41, "a\tb\x01"):
        with pytest.raises(ValueError, match="nickname"):
            store.nickname_of(bad)
    with pytest.raises(KeyError, match="No learner nope"):
        store.get_learner(db_session, "nope")


def test_deleting_a_learner_removes_everything_held_about_them(db_session: Session, fox: str) -> None:
    owl = store.add_learner(db_session, "Owl").id
    a = attempt(fox)
    store.record(db_session, a)
    store.record(db_session, attempt(owl))
    store.strike(db_session, a.event_id, "someone else")
    store.delete_learner(db_session, fox)
    count = lambda model: db_session.scalar(select(func.count()).select_from(model))  # noqa: E731
    assert (count(Learner), count(Sitting), count(Attempt), count(Tombstone)) == (1, 1, 1, 0)
    with pytest.raises(KeyError):
        store.delete_learner(db_session, fox)


# Attempts


def test_the_server_judges_the_first_answer_from_the_rebuilt_round(db_session: Session, fox: str) -> None:
    assert store.record(db_session, attempt(fox, right=True)).first_correct is True
    assert store.record(db_session, attempt(fox, seed=2, right=False)).first_correct is False
    placed = store.record(db_session, attempt(fox, mode=Mode.ORDER, seed=3, right=True, at=T0 + timedelta(minutes=1)))
    assert placed.first_correct is True
    row = db_session.get(Attempt, placed.event_id)
    assert row is not None
    assert row.options == 0
    assert row.mechanic == "sequence"
    assert row.skills[0] == {"skill": "maths.comparison.order", "role": "primary"}
    wrong_place = attempt(fox, mode=Mode.ORDER, seed=4, right=False)
    assert store.record(db_session, wrong_place).first_correct is False
    assert store.list_learners(db_session)[0].attempts == 4


def test_an_attempt_sent_twice_is_logged_once_and_a_changed_one_is_refused(db_session: Session, fox: str) -> None:
    a = attempt(fox)
    assert store.record(db_session, a).duplicate is False
    again = store.record(db_session, a.model_copy())
    assert again.duplicate is True
    assert again.first_correct is True
    with pytest.raises(store.Conflict, match="never rewritten"):
        store.record(db_session, a.model_copy(update={"asked": Mode.COUNTING}))
    assert db_session.scalar(select(func.count()).select_from(Attempt)) == 1


def test_sessions_span_their_attempts_and_belong_to_one_learner(db_session: Session, fox: str) -> None:
    sid = uuid.uuid4().hex
    store.record(db_session, attempt(fox, at=T0 + timedelta(minutes=5), session=sid))
    store.record(db_session, attempt(fox, seed=2, at=T0, session=sid))  # sent late, played first
    s = db_session.get(Sitting, sid)
    assert s is not None
    assert utc(s.started_at) == T0
    assert utc(s.last_at) == T0 + timedelta(minutes=5, seconds=4)
    owl = store.add_learner(db_session, "Owl").id
    with pytest.raises(store.Conflict, match="another learner"):
        store.record(db_session, attempt(owl, seed=3, session=sid))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"mode": Mode.MIXED}, "kind played"),
        ({"version": 9}, "version 9 is not kept"),
        ({"first_answer": store.FirstAnswer(option="nope")}, "not one of this round's options"),
        ({"first_answer": store.FirstAnswer(placement={"x": "first"})}, "not one of this round's options"),
        ({"tries": 3}, "ended there"),
        ({"answered_at": T0 - timedelta(seconds=1)}, "before presented_at"),
    ],
)
def test_attempts_that_cannot_be_true_are_refused(
    db_session: Session, fox: str, change: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        store.record(db_session, attempt(fox).model_copy(update=change))


def test_placing_and_wrong_answers_are_checked_too(db_session: Session, fox: str) -> None:
    order = attempt(fox, mode=Mode.ORDER, seed=3)
    with pytest.raises(ValueError, match="answered with a placement"):
        store.record(db_session, order.model_copy(update={"first_answer": store.FirstAnswer(option="a")}))
    with pytest.raises(ValueError, match="piece or place"):
        store.record(
            db_session, order.model_copy(update={"first_answer": store.FirstAnswer(placement={"zz": "first"})})
        )
    wrong = attempt(fox, right=False)
    with pytest.raises(ValueError, match="more than one try"):
        store.record(db_session, wrong.model_copy(update={"tries": 1}))
    with pytest.raises(ValueError, match="not both"):
        store.FirstAnswer(option="a", placement={})
    with pytest.raises(KeyError):
        store.record(db_session, attempt("0" * 32))


def test_struck_attempts_count_for_nothing_and_keep_their_first_reason(db_session: Session, fox: str) -> None:
    a = attempt(fox, right=False)
    store.record(db_session, a)
    store.strike(db_session, a.event_id, "  my   sibling was playing ")
    store.strike(db_session, a.event_id, "another reason")
    store.strike(db_session, store.record(db_session, attempt(fox, seed=5, at=T0 + timedelta(minutes=1))).event_id, "")
    log = store.events(db_session, fox)
    assert [e.struck for e in log] == ["my sibling was playing", "struck out by a grown-up"]
    reports = {r.skill: r for r in skill_reports(log, SKILLS)}
    assert reports["maths.counting.objects"].state is State.UNOBSERVED
    with pytest.raises(KeyError, match="No attempt"):
        store.strike(db_session, "nope", "x")


# Evidence rules


def event(
    *,
    right: bool,
    at: datetime = T0,
    skills: list[tuple[str, str]] | None = None,
    mechanic: str = "select_one",
    struck: str | None = None,
) -> Event:
    return Event(
        event_id=uuid.uuid4().hex,
        session_id="s",
        mode="counting",
        version=1,
        choices=4,
        seed=1,
        mechanic=mechanic,
        options=0 if mechanic == "give_n" else 4,
        skills=[
            SkillUse(skill=s, role=r)
            for s, r in skills
            or [
                ("maths.counting.objects", "primary"),
                ("maths.numerals.recognise", "confound"),
                ("maths.cardinality.last_number", "secondary"),
            ]
        ],
        asked="mixed",
        presented_at=at,
        answered_at=at,
        first_answer={"option": "n1"},
        first_correct=right,
        tries=1 if right else 2,
        outcome="right",
        struck=struck,
    )


def test_a_wrong_answer_is_held_back_until_its_confound_is_shown() -> None:
    log = [
        event(right=False),
        event(right=True, at=T0 + timedelta(minutes=1)),
        event(right=False, at=T0 + timedelta(minutes=2)),
    ]
    u = uses(log, {"maths.numerals.recognise": "Read a numeral"})
    counting = u["maths.counting.objects"]
    assert [(x.counted, x.why) for x in counting] == [
        (False, "could be Read a numeral, not yet shown"),
        (True, ""),
        (True, ""),
    ]
    assert [x.counted for x in u["maths.numerals.recognise"]] == [False, True, False]
    assert u["maths.cardinality.last_number"][2].why.startswith("a wrong answer counts only")


def test_the_estimators_fold_counted_answers() -> None:
    obs = [Observation("e", T0, c, 4, "select_one", "primary") for c in (True, True, False, True, True, True)]
    assert RULE.estimate(obs).model_dump() == {"model": "rule@1", "p": 0.8, "used": 5}
    assert RULE.estimate([]).p == 0.0
    # P(known) by hand for one right answer from the prior: Bayes' rule, then the chance of learning.
    one = BAYES.estimate(obs[:1])
    seen = 0.2 * 0.9 / (0.2 * 0.9 + 0.8 * 0.25)
    assert one.p == pytest.approx(seen + (1 - seen) * 0.1)
    assert one.used == 1
    wrong = BAYES.estimate([Observation("e", T0, False, 0, "give_n", "primary")])
    seen = 0.2 * 0.1 / (0.2 * 0.1 + 0.8 * (1 - PLACE_GUESS))
    assert wrong.p == pytest.approx(seen + (1 - seen) * 0.1)
    assert BAYES.estimate(obs).p > 0.9 > BAYES.estimate(obs[:2]).p


def test_reporting_states_climb_with_evidence_and_unobserved_is_its_own_state() -> None:
    skill = [("maths.counting.objects", "primary")]

    def state(log: list[Event]) -> State:
        return skill_reports(log, SKILLS[:1])[0].state

    assert state([]) is State.UNOBSERVED
    assert state([event(right=False, skills=skill)]) is State.INTRODUCED
    mixed = [event(right=i % 2 == 0, at=T0 + timedelta(minutes=i), skills=skill) for i in range(6)]
    assert state(mixed) is State.EMERGING
    taps = [event(right=True, at=T0 + timedelta(minutes=i), skills=skill) for i in range(5)]
    assert state(taps) is State.INDEPENDENT
    both = [*taps, event(right=True, at=T0 + timedelta(minutes=9), skills=skill, mechanic="give_n")]
    assert state(both) is State.GENERALISED
    later = [*both, event(right=True, at=T0 + timedelta(days=8), skills=skill)]
    assert state(later) is State.RETAINED
    assert state([*later, event(right=False, at=T0 + timedelta(days=9), skills=skill)]) is not State.RETAINED


def test_secondary_evidence_alone_never_makes_a_skill_independent() -> None:
    log = [event(right=True, at=T0 + timedelta(minutes=i)) for i in range(8)]
    r = {x.skill: x for x in skill_reports(log, SKILLS)}
    assert r["maths.counting.objects"].state is State.INDEPENDENT
    assert r["maths.cardinality.last_number"].state is State.EMERGING  # p is high, but it was never the one assessed
    assert r["maths.cardinality.last_number"].estimates[0].p > 0.85
    assert r["maths.subitising.perceptual"].state is State.UNOBSERVED
    assert r["maths.subitising.perceptual"].estimates == []


def test_a_skill_the_packs_no_longer_name_is_still_reported_by_its_id() -> None:
    r = skill_reports([event(right=True, skills=[("maths.gone", "primary")])], SKILLS[:1])
    assert [x.skill for x in r] == ["maths.counting.objects", "maths.gone"]
    assert r[1].title == "maths.gone"


# Replay: the exit criterion


def test_rebuilding_from_the_log_reproduces_identical_estimates(db_session: Session, fox: str) -> None:
    rng = random.Random(7)
    sent = [
        attempt(
            fox,
            mode=rng.choice([Mode.COUNTING, Mode.QUICK_LOOK, Mode.GIVE, Mode.ORDER]),
            seed=i,
            right=rng.random() < 0.7,
            at=T0 + timedelta(hours=i),
        )
        for i in range(60)
    ]
    for a in sent:
        store.record(db_session, a)
    store.strike(db_session, sent[3].event_id, "a sibling")
    saved = store.export(db_session, fox, SKILLS)
    assert store.rebuild(saved) == []
    assert store.rebuild(store.Export.model_validate_json(saved.model_dump_json())) == []  # through the file format
    # The same attempts arriving in another order (a queue replayed) give the same estimates.
    owl = store.add_learner(db_session, "Owl", at=T0).id
    shuffled = sent[:]
    rng.shuffle(shuffled)
    for a in shuffled:
        store.record(
            db_session,
            a.model_copy(update={"learner_id": owl, "event_id": a.event_id[::-1], "session_id": "5e55" + owl[4:]}),
        )
    store.strike(db_session, sent[3].event_id[::-1], "a sibling")
    assert store.profile(db_session, owl, SKILLS).skills == saved.skills
    # And a change to the log is caught.
    tampered = saved.model_copy(update={"events": saved.events[1:]})
    assert store.rebuild(tampered) != []


def test_differences_name_every_change() -> None:
    a = skill_reports([event(right=True, skills=[("maths.numerals.recognise", "primary")])], SKILLS[:2])
    b = skill_reports([], SKILLS[1:3])
    found = differences(a, b)
    assert "maths.counting.objects: only in the saved report" in found
    assert "maths.cardinality.last_number: only in the rebuilt report" in found
    assert any(x.startswith("maths.numerals.recognise: state was 'introduced'") for x in found)


def test_profile_export_and_evidence_rows(db_session: Session, fox: str) -> None:
    store.record(db_session, attempt(fox, right=False))
    store.record(db_session, attempt(fox, mode=Mode.GIVE, seed=2, at=T0 + timedelta(minutes=1)))
    p = store.profile(db_session, fox, SKILLS)
    assert p.learner.attempts == 2
    assert p.sessions == 1
    assert p.struck == 0
    assert [m.model for m in p.models] == ["bkt@1", "rule@1"]
    out = store.export(db_session, fox, SKILLS, at=T0)
    assert out.format == "flashtap-learner@3"
    assert out.decisions == []
    assert out.sessions[0].policy is None
    assert len(out.events) == 2
    assert len(out.sessions) == 1
    assert store.rebuild(out) == []
    # A log already read is the one reported on, so an export's events and estimates come from one read.
    assert all(s.state == "unobserved" for s in store.profile(db_session, fox, SKILLS, log=[]).skills)
    rows = evidence_rows(store.events(db_session, fox), "maths.counting.objects", {})
    assert len(rows) == 1
    assert rows[0].answer.isdigit()
    assert rows[0].counted is False
    assert "maths.numerals.recognise" in rows[0].why
    give = evidence_rows(store.events(db_session, fox), "maths.cardinality.give_n", {})
    assert give[0].answer == "an arrangement"
    assert give[0].correct
    old = store.events(db_session, fox)[0].model_copy(update={"version": 9})
    assert evidence_rows([old], "maths.counting.objects", {})[0].answer == old.first_answer["option"]
    # The packs a round drew from are logged with it and exported; a round from packs since changed is not rebuilt
    # from today's words (its answer could name another picture), and one logged before packs were recorded is.
    first = store.events(db_session, fox)[0]
    assert first.content == rounds.content_of(Mode.COUNTING) == out.events[0].content
    stale = first.model_copy(update={"content": {**first.content, "words": first.content["words"] + 1}})
    assert evidence_rows([stale], "maths.counting.objects", {})[0].answer == first.first_answer["option"]
    unrecorded = first.model_copy(update={"content": {}})
    assert evidence_rows([unrecorded], "maths.counting.objects", {})[0].answer == rows[0].answer


# Where the records live


def test_with_no_database_configured_the_records_go_beside_the_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    for var in ("STRATA_DB_URL", "FLASHTAP_DATABASE_URL", "STRATA_DB_DATABASE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FLASHTAP_HOME", str(tmp_path / "home"))
    assert learner_db.default_url() == "sqlite:///" + str(tmp_path / "home" / "learners.db")
    engine = learner_db.open_engine()
    with Session(engine) as s:
        assert store.add_learner(s, "Fox").nickname == "Fox"
    engine.dispose()
    assert (tmp_path / "home" / "learners.db").exists()


def test_the_package_declaration_is_the_one_pyproject_names(db_project) -> None:
    # Project.load(__file__) reads src/flashtap/strata-db.toml, which an installed wheel ships; strata-db and the
    # pytest plugin reach it through pyproject.toml's `file`. Both must land on the same project.
    p = learner_db.PROJECT
    assert (p.app, p.models, p.migrations_dir, p.schema) == (
        db_project.app,
        db_project.models,
        db_project.migrations_dir,
        db_project.schema,
    )
