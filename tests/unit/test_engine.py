"""The adaptive engine (src/flashtap/engine/): the learner model, the policy's limits, filters, utilities and seeded
draw, scoring, simulated learners, and sessions and replays on a real migrated database. Learners are invented."""

import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from flashtap import rounds
from flashtap.engine import evaluate, model, policy, replay, sessions, simulate
from flashtap.engine.model import Graph, Knowledge, Params, fold
from flashtap.engine.policy import POLICY, Action, Config, Past, SetAside, Why, decide, explain
from flashtap.learners import db as learner_db
from flashtap.learners import store
from flashtap.learners.evidence import Event, SkillUse
from flashtap.learners.models import Attempt, Decision, Sitting
from flashtap.mechanics import Mode

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
G = model.graph()
CONFIG = Config(choices=4, tries=0)
COUNT = "maths.counting.objects"
LAST = "maths.cardinality.last_number"
GIVE = "maths.cardinality.give_n"
NUMERAL = "maths.numerals.recognise"
ONE_TO_ONE = "maths.counting.one_to_one"


def event(
    mode: Mode = Mode.COUNTING,
    *,
    right: bool = True,
    at: datetime = T0,
    session: str = "s1",
    struck: str | None = None,
    received: datetime | None = None,
    struck_at: datetime | None = None,
) -> Event:
    shape = model.SHAPE[mode]
    return Event(
        event_id=uuid.uuid4().hex,
        session_id=session,
        mode=mode.value,
        version=shape.version,
        choices=4,
        seed=1,
        mechanic=shape.mechanic.value,
        options=shape.options(4),
        skills=[SkillUse(skill=s, role=r) for s, r in shape.roles],
        asked="next",
        presented_at=at,
        answered_at=at + timedelta(seconds=3),
        first_answer={},
        first_correct=right,
        tries=1,
        outcome="right",
        struck=struck,
        received_at=received,
        struck_at=struck_at,
    )


# The model


def test_graph_closes_strong_prerequisites_over_the_skills_the_rounds_assess() -> None:
    assert {COUNT, ONE_TO_ONE, "maths.verbal_count.forwards"} <= G.before[LAST]
    assert G.before[GIVE] >= G.before[LAST] | {LAST}
    assert GIVE in G.after[COUNT]
    assert G.depth(ONE_TO_ONE) == 0
    assert G.depth(GIVE) == 3
    small = model.graph(skills=[GIVE, COUNT])  # a chain through a skill left out still links its ends
    assert small.before == {GIVE: frozenset({COUNT}), COUNT: frozenset()}
    assert small.after[COUNT] == frozenset({GIVE})


def test_a_right_answer_places_unseen_prerequisites_and_a_wrong_one_unseen_dependents() -> None:
    k = fold([event(Mode.GIVE)], G)
    assert k.p(GIVE) > 0.5
    assert k.p(LAST) == pytest.approx(0.9 * k.p(GIVE))  # unseen: inferred from the graph
    assert k.state(LAST).own == 0

    k = fold([event(Mode.COUNTING), event(Mode.COUNTING, right=False, at=T0 + timedelta(minutes=1))], G)
    assert k.state(COUNT).own == 2
    assert k.p(GIVE) <= k.p(COUNT)  # unseen dependents fall to it
    # A skill's own evidence is never overwritten from the graph, either way.
    gave = [event(Mode.GIVE)]
    seen = fold([*gave, event(Mode.COUNTING, right=False, at=T0 + timedelta(minutes=1))], G)
    assert seen.state(GIVE).own == 1
    assert seen.p(GIVE) == pytest.approx(fold(gave, G).p(GIVE))
    missed = [
        event(Mode.MISSING),
        event(Mode.COUNTING, right=False, at=T0 + timedelta(minutes=1)),
    ]  # the numeral shown first
    assert fold(missed, G).state(COUNT).own == 1
    lifted = fold([*missed, event(Mode.GIVE, at=T0 + timedelta(minutes=2))], G)
    assert lifted.p(COUNT) == pytest.approx(fold(missed, G).p(COUNT))


def test_a_round_is_predicted_from_every_skill_it_needs() -> None:
    k = Knowledge(G, Params(prior=0.5, slip=0.1))
    one = k.p_right([COUNT], 4)
    assert one == pytest.approx(0.5 * 0.9 + 0.5 * 0.25)
    assert k.p_right([COUNT, LAST], 4) == pytest.approx(0.25 * 0.9 + 0.75 * 0.25)
    assert k.p_right([GIVE], 0) == pytest.approx(0.5 * 0.9 + 0.5 * 0.05)  # an arrangement is rarely right by luck
    assert Params().label() == "prior 0.2, learn 0.1, slip 0.1"


def test_retention_doubles_after_a_spaced_right_answer_and_halves_after_a_miss() -> None:
    k = Knowledge(G)
    assert k.state(COUNT).recall(T0) == 0.0  # never right: nothing to recall
    k.observe(event(Mode.GIVE))  # right: the confounds are shown, so later misses count
    k.observe(event(Mode.COUNTING, at=T0))
    s = k.state(COUNT)
    assert s.half_life == 1.0
    assert s.recall(T0 + timedelta(days=1)) == pytest.approx(0.5)
    k.observe(event(Mode.COUNTING, at=T0 + timedelta(hours=1)))  # the same day: no spacing
    assert s.half_life == 1.0
    k.observe(event(Mode.COUNTING, at=T0 + timedelta(days=2)))
    assert s.half_life == 2.0
    k.observe(event(Mode.COUNTING, right=False, at=T0 + timedelta(days=3)))
    assert s.half_life == 1.0
    assert s.recall(s.last_right - timedelta(days=1)) == 1.0  # never above 1


def test_a_wrong_answer_held_back_for_an_unseen_confound_moves_nothing() -> None:
    k = fold([event(Mode.COUNTING, right=False)], G)
    assert k.counted == 0
    assert k.p(COUNT) == Params().prior


def test_the_same_log_in_any_order_folds_to_the_same_knowledge() -> None:
    log = [event(random.choice(list(model.SHAPE)), right=i % 3 != 0, at=T0 + timedelta(minutes=i)) for i in range(40)]
    a = fold(log, G)
    b = fold(random.sample(log, len(log)), G)
    assert {s: (x.p, x.own, x.half_life) for s, x in a.skills.items()} == {
        s: (x.p, x.own, x.half_life) for s, x in b.skills.items()
    }


# The policy


def past(*answers: tuple[Mode, bool], breaks: tuple[int, ...] = (), started: datetime = T0) -> Past:
    decisions: list[tuple[Action, Mode | None]] = []
    for i, (m, _) in enumerate(answers):
        if i in breaks:
            decisions.append((Action.BREAK, None))
        decisions.append((Action.ROUND, m))
    return Past(started=started, decisions=decisions, answers=list(answers))


def test_the_session_ends_at_its_rounds_or_minutes() -> None:
    k = Knowledge(G)
    full = past(*[(Mode.MATCHING, True)] * 20)
    c = decide(k, full, CONFIG, "s:20", T0)
    assert (c.action, c.rationale, c.probability, c.candidates) == (Action.END, [Why.CAP_ROUNDS], 1.0, [])
    c = decide(k, past(), CONFIG, "s:0", T0 + timedelta(minutes=15))
    assert (c.action, c.rationale) == (Action.END, [Why.CAP_MINUTES])
    assert explain(c, {}, CONFIG, 3) == "A session is 15 minutes at most."


def test_breaks_are_offered_after_misses_and_every_few_rounds_never_twice_running() -> None:
    k = Knowledge(G)
    missed = past((Mode.MATCHING, True), *[(Mode.COUNTING, False)] * 3)
    c = decide(k, missed, CONFIG, "s:4", T0)
    assert (c.action, c.rationale) == (Action.BREAK, [Why.FRUSTRATION])
    after = Past(T0, [*missed.decisions, (Action.BREAK, None)], missed.answers)
    assert decide(k, after, CONFIG, "s:5", T0).action is Action.ROUND
    ten = past(*[(Mode.MATCHING, True)] * 10)
    c = decide(k, ten, CONFIG, "s:10", T0)
    assert (c.action, c.rationale) == (Action.BREAK, [Why.BREAK_DUE])
    assert explain(c, {}, CONFIG, 10) == "10 rounds played so far."
    assert explain(c, {}, CONFIG, 1) == "1 round played so far."
    assert ten.since_break() == 10
    assert past(*[(Mode.MATCHING, True)] * 3, breaks=(2,)).since_break() == 1
    assert missed.misses() == 3


def test_every_eligible_candidate_has_a_logged_chance_and_the_draw_is_seeded() -> None:
    k = Knowledge(G)
    c = decide(k, past(), CONFIG, "s:0", T0)
    assert c.action is Action.ROUND
    assert len(c.candidates) == len(rounds.TEMPLATES)
    open_ = [x for x in c.candidates if x.set_aside is None]
    assert sum(x.probability for x in open_) == pytest.approx(1.0)
    assert min(x.probability for x in open_) >= POLICY.epsilon / len(open_)
    assert c.probability == next(x.probability for x in c.candidates if x.mode is c.mode)
    assert (c.version, c.choices) == (1, 4)
    assert c.seed is not None
    assert decide(k, past(), CONFIG, "s:0", T0) == c
    picks = {decide(k, past(), CONFIG, f"s:{i}", T0).mode for i in range(60)}
    assert len(picks) > 3  # exploration: more than the top pick comes up


def test_candidates_are_labelled_by_what_they_would_do_for_their_skill() -> None:
    k = Knowledge(G)
    first = {x.mode: x.action for x in decide(k, past(), CONFIG, "s:0", T0).candidates}
    assert set(first.values()) == {Why.PLACEMENT}
    log = [event(Mode.MATCHING, at=T0 + timedelta(minutes=i)) for i in range(policy.PLACING)]
    k = fold(log, G)
    soon = T0 + timedelta(hours=1)
    cands = {x.mode: x for x in decide(k, past(started=soon), CONFIG, "s:0", soon).candidates}
    assert cands[Mode.COUNTING].action is Why.INTRODUCE
    assert cands[Mode.MATCHING].action is Why.CONSOLIDATE
    days = T0 + timedelta(days=3)
    later = {x.mode: x for x in decide(k, past(started=days), CONFIG, "s:0", days).candidates}
    assert later[Mode.MATCHING].action is Why.REVIEW
    assert later[Mode.MATCHING].retention > 0.8
    k = fold([*log, event(Mode.COLOURS, right=False, at=T0 + timedelta(minutes=30))], G)
    assert {x.mode: x for x in decide(k, past(), CONFIG, "s:0", T0).candidates}[Mode.COLOURS].action is Why.PRACTISE


def test_a_known_gap_in_a_prerequisite_sets_a_round_aside() -> None:
    log = [
        event(Mode.MATCHING),
        *(event(Mode.CAPITALS, right=False, at=T0 + timedelta(minutes=i)) for i in range(1, 4)),
    ]
    log += [event(Mode.SORT_SOUNDS, right=False, at=T0 + timedelta(minutes=9))]
    k = fold(log, G)
    k.state("literacy.letters.identify").own = 2  # as if seen twice and still not known
    k.state("literacy.letters.identify").p = 0.1
    cands = {x.mode: x for x in decide(k, past(), CONFIG, "s:0", T0).candidates}
    assert cands[Mode.CAPITALS].set_aside is SetAside.PREREQUISITE
    assert cands[Mode.CAPITALS].probability == 0.0
    assert cands[Mode.MATCHING].set_aside is None


def test_after_two_misses_only_likely_rounds_are_offered_and_never_the_same_three_times() -> None:
    log = [event(Mode.MATCHING, at=T0 + timedelta(minutes=i)) for i in range(5)]
    k = fold(log, G)
    two = past((Mode.COUNTING, False), (Mode.COUNTING, False))
    c = decide(k, two, CONFIG, "s:2", T0)
    assert Why.EASIER in c.rationale
    cands = {x.mode: x for x in c.candidates}
    assert cands[Mode.GIVE].set_aside is SetAside.FRUSTRATION
    assert cands[Mode.COUNTING].set_aside in (SetAside.FRUSTRATION, SetAside.REPEAT)
    assert cands[Mode.MATCHING].set_aside is None
    assert c.mode is not Mode.COUNTING
    assert explain(c, {}, CONFIG, 2).endswith("One likely to go right, after a few misses.")
    again = past((Mode.MATCHING, True), (Mode.MATCHING, True))
    assert {x.mode: x for x in decide(k, again, CONFIG, "s:2", T0).candidates}[
        Mode.MATCHING
    ].set_aside is SetAside.REPEAT


def test_when_every_round_is_set_aside_the_softer_filters_give_way() -> None:
    k = Knowledge(G)  # nothing known: every round is unlikely to go right
    c = decide(k, past((Mode.COUNTING, False), (Mode.COUNTING, False)), CONFIG, "s:2", T0)
    assert all(x.set_aside is not None for x in c.candidates)
    assert c.action is Action.ROUND
    assert sum(x.probability for x in c.candidates) == pytest.approx(1.0)


def test_a_missed_round_is_followed_by_contrasts_that_leave_part_of_it_out() -> None:
    k = Knowledge(G)
    failed = past((Mode.COUNTING, False))
    cands = {x.mode: x for x in decide(k, failed, CONFIG, "s:1", T0).candidates}
    assert cands[Mode.MISSING].contrast  # shares reading the numeral, leaves out counting
    assert cands[Mode.MISSING].diagnostic > 0
    assert not cands[Mode.MATCHING].contrast  # shares nothing
    assert not cands[Mode.COUNTING].contrast  # the same round is not a contrast
    keen = policy.Policy(weights=policy.Weights(diagnostic=50), epsilon=0.0)
    c = decide(k, failed, CONFIG, "s:1", T0, keen)
    assert Why.CONTRAST in c.rationale
    assert "leaves out part of the last round" in explain(c, {}, CONFIG, 1)


def test_a_pick_below_the_top_says_it_was_exploration() -> None:
    k = Knowledge(G)
    for i in range(200):
        c = decide(k, past(), CONFIG, f"x:{i}", T0)
        if Why.EXPLORE in c.rationale:
            assert c.probability < max(x.probability for x in c.candidates)
            assert "chosen by chance" in explain(c, {}, CONFIG, 0)
            break
    else:
        pytest.fail("200 draws never explored")


def test_rationale_in_words_names_the_skill() -> None:
    titles = {COUNT: "Count a set of things"}
    for why, said in [
        (Why.PLACEMENT, "Finding where to start, a first look at: Count a set of things."),
        (Why.INTRODUCE, "Something new: Count a set of things."),
        (Why.PRACTISE, "Practising: Count a set of things."),
        (Why.REVIEW, "Back for review, so it is not forgotten: Count a set of things."),
        (Why.CONSOLIDATE, "Keeping it going: Count a set of things."),
    ]:
        c = policy.Choice(policy="utility@1", action=Action.ROUND, skill=COUNT, rationale=[why], probability=0.5)
        assert explain(c, titles, CONFIG, 0) == said
    c = policy.Choice(policy="utility@1", action=Action.END, rationale=[Why.CAP_ROUNDS], probability=1)
    assert explain(c, titles, CONFIG, 20) == "A session is 20 rounds at most."
    assert policy.entropy(0.5) == 1.0
    assert policy.entropy(0.0) == policy.entropy(1.0) == 0.0


# Scoring and simulated learners


def test_scores_are_log_loss_and_brier_best_first() -> None:
    s = evaluate.score("m", "d", [(0.5, True), (0.5, False)])
    assert s.log_loss == pytest.approx(0.693147, abs=1e-6)
    assert s.brier == 0.25
    assert evaluate.score("m", "d", [(1.0, False)]).log_loss == pytest.approx(
        13.815511, abs=1e-5
    )  # clipped, not infinite
    assert evaluate.score("m", "d", []).attempts == 0
    log = [event(Mode.MATCHING, right=i % 4 != 0, at=T0 + timedelta(minutes=i)) for i in range(20)]
    log.append(event(Mode.MATCHING, struck="someone else", at=T0 + timedelta(hours=1)))
    out = evaluate.scores([log], G)
    assert [x.attempts for x in out] == [20, 20, 20]  # the struck attempt is not predicted
    assert out == sorted(out, key=lambda x: x.log_loss)
    assert evaluate.rule_pairs(log[:1], 5, 0.6)[0] == (0.6, False)  # no answers yet: the base rate
    f = evaluate.fit([log], G)
    assert f.window in evaluate.WINDOWS
    assert f.base == 0.75


def test_simulated_learners_follow_the_graph_and_replay_from_their_seed() -> None:
    rng = random.Random(3)
    sims = [simulate.learner(i, G, rng) for i in range(30)]
    for s in sims:
        assert all(G.before[k] <= s.known for k in s.known)
    log = simulate.play(sims[0], G, 2, None)
    assert {e.asked for e in log} == {"mixed"}
    assert len(log) == 2 * simulate.CONFIG.max_rounds
    a = simulate.report(learners=8, sessions=2, seed=5)
    assert a == simulate.report(learners=8, sessions=2, seed=5)
    assert (a.trained_on, a.held_out) == (5, 3)
    assert [g.policy for g in a.gains] == [POLICY.id, "random"]
    assert a.gains[0].known_before == a.gains[1].known_before
    assert a.beats_rule == (
        next(x for x in a.scores if x.model == "engine").log_loss
        < next(x for x in a.scores if x.model == "rule").log_loss
    )
    lines = simulate.describe(a)
    assert lines[0] == f"8 simulated learners, 2 sessions each, seed 5: {a.attempts} attempts"
    assert lines[-1].startswith("the engine's model ")
    assert (
        simulate.describe(a.model_copy(update={"beats_rule": False}))[-1]
        == "the engine's model does NOT beat the rule baseline"
    )
    with pytest.raises(ValueError, match="at least 4"):
        simulate.report(learners=3)


def test_on_simulated_learners_the_engine_predicts_held_out_answers_better_than_the_rule() -> None:
    """The plan's exit criterion for PR 5, at a size the unit suite can afford (`flashtap engine simulate` runs 200)."""
    r = simulate.report(learners=40, sessions=4, seed=1)
    assert r.beats_rule
    by = {x.model: x for x in r.scores}
    assert by["engine"].brier < by["rule"].brier


# Sessions and replay, on the learner records


@pytest.fixture
def fox(db_session: Session) -> str:
    return store.add_learner(db_session, "Fox", at=T0).id


TITLES = {COUNT: "Count a set of things"}


def answer(db: Session, n: sessions.Next, learner: str, *, right: bool, at: datetime | None) -> store.Ack:
    """Answer the decision's round; `at` None stamps it with the clock, as the server does."""
    shown = at or datetime.now(UTC)
    r = n.round
    assert r is not None
    if r.places:
        first = store.FirstAnswer(placement={k: s.id for s in r.places for k in s.takes[: s.holds]} if right else {})
    else:
        first = store.FirstAnswer(option=r.answer if right else next(o.id for o in r.options if not o.correct))
    return store.record(
        db,
        store.AttemptIn(
            event_id=uuid.uuid4().hex,
            learner_id=learner,
            session_id=n.session_id,
            mode=r.mode,
            version=r.version,
            choices=r.choices,
            seed=r.seed,
            asked="next",
            presented_at=shown,
            answered_at=shown + timedelta(seconds=4),
            first_answer=first,
            tries=1 if right else 2,
            outcome="right",
            decision_id=n.id,
        ),
        at=at + timedelta(seconds=5) if at else None,
    )


def play_session(
    db: Session, learner: str, config: Config, start: datetime, rights: float = 0.7, seed: int = 0
) -> list[sessions.Next]:
    """Ask for decisions until the session ends, answering each round (right with chance `rights`)."""
    rng = random.Random(seed)
    info = sessions.start(db, learner, config, at=start)
    out: list[sessions.Next] = []
    at = start
    for seq in range(100):
        n = sessions.next_decision(db, info.id, seq, G, TITLES, at=at)
        out.append(n)
        if n.action is Action.END:
            break
        if n.action is Action.ROUND:
            answer(db, n, learner, right=rng.random() < rights, at=at + timedelta(seconds=1))
        at += timedelta(seconds=30)
    return out


def test_a_session_plans_rounds_breaks_and_its_end(db_session: Session, fox: str) -> None:
    config = Config(choices=3, tries=2, max_rounds=5, break_every=2)
    made = play_session(db_session, fox, config, T0)
    assert [n.action for n in made] == [
        Action.ROUND,
        Action.ROUND,
        Action.BREAK,
        Action.ROUND,
        Action.ROUND,
        Action.BREAK,
        Action.ROUND,
        Action.END,
    ]
    assert [n.seq for n in made] == list(range(8))
    first = made[0]
    assert first.round is not None
    assert (first.round.choices, first.round.tries) == (3, 2)  # the session's settings, not today's
    assert first.skill == model.SHAPE[first.round.mode].primary
    assert first.rationale[0] is Why.PLACEMENT
    assert first.why.startswith("Finding where to start")
    assert made[2].why == "2 rounds played so far."
    assert made[-1].rounds_played == 5
    assert made[-1].why == "A session is 5 rounds at most."
    sitting = db_session.get(Sitting, first.session_id)
    assert sitting is not None
    assert sitting.started_at.replace(tzinfo=UTC) == T0  # an engine session keeps its start
    assert sitting.policy == POLICY.id
    assert sitting.config == config.model_dump()


def test_asking_again_returns_the_same_decision_and_the_numbers_are_kept(db_session: Session, fox: str) -> None:
    info = sessions.start(db_session, fox, CONFIG, at=T0)
    a = sessions.next_decision(db_session, info.id, 0, G, TITLES, at=T0)
    assert sessions.next_decision(db_session, info.id, 0, G, TITLES, at=T0 + timedelta(minutes=1)) == a
    with pytest.raises(ValueError, match="number 1, not 3"):
        sessions.next_decision(db_session, info.id, 3, G, TITLES)
    with pytest.raises(KeyError, match="No engine session"):
        sessions.next_decision(db_session, "f" * 32, 0, G, TITLES)
    with pytest.raises(KeyError, match="No learner"):
        sessions.start(db_session, "f" * 32, CONFIG)
    ended = play_session(db_session, fox, Config(choices=4, tries=0, max_rounds=1), T0)
    with pytest.raises(store.Conflict, match="session has ended"):
        sessions.next_decision(db_session, ended[0].session_id, len(ended), G, TITLES)


def test_an_attempt_names_its_decision_once_and_must_match_it(db_session: Session, fox: str) -> None:
    info = sessions.start(db_session, fox, CONFIG, at=T0)
    n = sessions.next_decision(db_session, info.id, 0, G, TITLES, at=T0)
    assert n.round is not None
    other = n.model_copy(update={"round": rounds.generate(n.round.mode, 4, (n.round.seed + 1) % rounds.SEED_LIMIT)})
    with pytest.raises(ValueError, match="chose a different round"):
        answer(db_session, other, fox, right=True, at=T0)
    with pytest.raises(ValueError, match="No decision"):
        answer(db_session, n.model_copy(update={"id": "b" * 32}), fox, right=True, at=T0)
    owl = store.add_learner(db_session, "Owl").id
    with pytest.raises(ValueError, match="No decision"):
        answer(db_session, n, owl, right=True, at=T0)
    answer(db_session, n, fox, right=True, at=T0)
    with pytest.raises(store.Conflict, match="already answered"):
        answer(db_session, n, fox, right=False, at=T0 + timedelta(seconds=1))


def test_replay_remakes_every_logged_decision_even_after_a_strike(db_session: Session, fox: str) -> None:
    play_session(db_session, fox, Config(choices=4, tries=0, max_rounds=8, break_every=4), T0)
    play_session(db_session, fox, Config(choices=4, tries=0, max_rounds=6), T0 + timedelta(days=2), seed=1)
    first = store.events(db_session, fox)[0]
    store.strike(db_session, first.event_id, "someone else was playing", at=T0 + timedelta(days=5))
    out = sessions.evaluate(db_session, sessions.ReplayIn(learner_id=fox), G)
    assert out.decisions == len(store.decisions(db_session, fox)) > 10
    assert (out.reproduced, out.differences) == (out.decisions, [])
    assert out.simulation is None
    assert {s.model for s in out.scores} == {"engine", "bkt", "rule"}
    assert out.scores[0].attempts == len(store.events(db_session, fox)) - 1

    saved = store.export(db_session, fox, [])
    assert saved.format == "flashtap-learner@3"
    assert saved.sessions[0].config is not None
    starts = {x.id: (x.started_at, x.config) for x in saved.sessions}
    assert replay.replay(saved.events, saved.decisions, starts, G) == (out.decisions, [])


def test_replay_names_a_decision_that_comes_out_different(db_session: Session, fox: str) -> None:
    made = play_session(db_session, fox, Config(choices=4, tries=0, max_rounds=3), T0)
    db_session.execute(update(Decision).where(Decision.id == made[1].id).values(probability=0.123))
    db_session.execute(update(Decision).where(Decision.id == made[2].id).values(candidates=[]))
    db_session.commit()
    out = sessions.evaluate(db_session, sessions.ReplayIn(learner_id=fox), G)
    assert out.reproduced == out.decisions - 2
    assert (
        out.differences[0]
        == f"decision 1 of session {made[1].session_id}: probability was 0.123, remade {made[1].probability!r}"
    )
    assert out.differences[1] == f"decision 2 of session {made[2].session_id}: the candidates differ"

    log = store.events(db_session, fox)
    old = store.decisions(db_session, fox)
    retired = [d.model_copy(update={"policy": "utility@0"}) for d in old[:1]]
    assert replay.replay(log, retired, {}, G) == (
        0,
        [f"decision 0 of session {old[0].session_id}: made by utility@0, which is not kept (now {POLICY.id})"],
    )
    assert replay.replay(log, old[:1], {}, G)[1] == [
        f"decision 0 of session {old[0].session_id}: its session's start and settings are not in the log"
    ]
    # A decision for a round drawn from packs since changed is reported, not remade: its round cannot be rebuilt.
    d = next(x for x in old if x.mode is not None)
    assert d.content == rounds.content_of(d.mode)  # recorded as its attempt records it
    moved = d.model_copy(update={"content": {**d.content, "words": 0}})
    now, was = (", ".join(f"{k}@{v}" for k, v in sorted(c.items())) for c in (d.content, moved.content or {}))
    assert replay.replay(log, [moved], {}, G) == (
        0,
        [f"decision {d.seq} of session {d.session_id}: made from {was}, which are not kept (now {now})"],
    )


def test_the_log_as_it_stood_counts_only_what_was_received_and_struck_by_then() -> None:
    a = event(at=T0, received=T0 + timedelta(minutes=1))
    b = event(at=T0, struck="not them", struck_at=T0 + timedelta(minutes=5))
    c = event(at=T0)  # an export from before 0.6.0: received when answered
    assert replay.received(c) == c.answered_at
    then = replay.as_of([a, b, c], T0 + timedelta(seconds=30))
    assert [e.event_id for e in then] == [b.event_id, c.event_id]
    assert then[0].struck is None
    assert replay.as_of([b], T0 + timedelta(minutes=6))[0].struck == "not them"


def test_evaluate_refuses_another_policy_and_runs_a_simulation(db_session: Session, fox: str) -> None:
    with pytest.raises(ValueError, match="Only the current policy"):
        sessions.evaluate(db_session, sessions.ReplayIn(policy="utility@0", learner_id=fox), G)
    with pytest.raises(ValueError, match="learner_id or a simulated"):
        sessions.ReplayIn()
    with pytest.raises(KeyError, match="No learner"):
        sessions.evaluate(db_session, sessions.ReplayIn(learner_id="f" * 32), G)
    out = sessions.evaluate(
        db_session, sessions.ReplayIn(simulated=sessions.SimulatedIn(learners=6, sessions=1, seed=2)), G
    )
    assert out.dataset == "simulated: 6 learners, 1 sessions, seed 2"
    assert out.simulation is not None
    assert out.scores == out.simulation.scores


def test_deleting_a_learner_deletes_their_decisions(db_session: Session, fox: str) -> None:
    play_session(db_session, fox, Config(choices=4, tries=0, max_rounds=2), T0)
    assert db_session.scalars(select(Decision)).all()
    store.delete_learner(db_session, fox)
    assert db_session.scalars(select(Decision)).all() == []
    assert db_session.scalars(select(Attempt)).all() == []


def test_a_graph_with_no_edges_is_each_skill_alone() -> None:
    k = Knowledge(Graph((), {}, {}))
    k.observe(event(Mode.GIVE))
    assert k.state(LAST).own == 0
    assert k.p(LAST) == Params().prior


def test_answers_and_decisions_sent_at_once_still_replay_exactly() -> None:
    """Each answer is sent at the same moment as the request for the next decision, on its own connection, as a
    browser that does not wait would. The learner's lock orders them, so every decision replays from the log as it
    stood, whichever came first; and two requests for one number get one decision."""
    bind = learner_db.open_engine()  # the test's own database file (db_env): a connection per thread, as a server has
    with Session(bind) as s:
        fox = store.add_learner(s, "Fox").id
        info = sessions.start(
            s, fox, Config(choices=4, tries=0, max_rounds=12, break_every=50)
        )  # now: decisions use the clock
    with Session(bind) as s:
        n = sessions.next_decision(s, info.id, 0, G, TITLES)
    for seq in range(1, 13):
        if n.action is not Action.ROUND:
            break

        def send(n: sessions.Next = n, seq: int = seq) -> None:
            with Session(bind) as s:
                answer(s, n, fox, right=seq % 3 != 0, at=None)

        def ask(seq: int = seq) -> sessions.Next:
            with Session(bind) as s:
                return sessions.next_decision(s, info.id, seq, G, TITLES)

        with ThreadPoolExecutor(3) as pool:
            sent, a, b = pool.submit(send), pool.submit(ask), pool.submit(ask)
            sent.result()
            n = a.result()
            assert b.result() == n
    assert n.action is Action.END
    with Session(bind) as s:
        out = sessions.evaluate(s, sessions.ReplayIn(learner_id=fox), G)
    bind.dispose()
    assert out.decisions == 13
    assert (out.reproduced, out.differences) == (out.decisions, [])
