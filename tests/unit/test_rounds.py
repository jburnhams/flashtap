import pytest
from hypothesis import given
from hypothesis import strategies as st

from flashtap import lexicon, rounds
from flashtap import mechanics as mx
from flashtap.mechanics import (
    CHOOSE,
    PLACE,
    InvalidRound,
    Mechanic,
    Mode,
    Option,
    Piece,
    Place,
    QRole,
    Round,
    SkillRole,
)
from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, TEMPLATES

modes = st.sampled_from(list(Mode))
choice_counts = st.integers(MIN_CHOICES, MAX_CHOICES)
seeds = st.integers(0, rounds.SEED_LIMIT - 1)


# The plan's exit for the mechanics (PR 3): every template, 1,000 seeds, every choice count, no ambiguous key. generate()
# runs mechanics.check on each; the loop restates the rules that matter from the outside.
@pytest.mark.parametrize("mode", rounds.PLAYABLE)
def test_a_thousand_seeds_of_every_template_give_one_unmistakable_answer(mode):
    for seed in range(1000):
        choices = MIN_CHOICES + seed % (MAX_CHOICES - MIN_CHOICES + 1)
        r = rounds.generate(mode, choices, seed)
        assert (r.mode, r.version, r.mechanic) == (mode, TEMPLATES[mode].version, TEMPLATES[mode].mechanic)
        if r.mechanic in CHOOSE:
            assert [o.id for o in r.options if o.correct] == [r.answer]
            assert len(r.options) == choices
            assert len({o.picture for o in r.options}) == choices
        else:
            homes = [k for s in r.places for k in s.takes]
            assert len(homes) == len(set(homes))  # no piece belongs in two places
            assert not mx.arranged_right(r, {})  # nothing is right before the learner moves anything
            assert mx.arranged_right(r, {k: s.id for s in r.places for k in s.takes[: s.holds]})


@given(modes, choice_counts, seeds)
def test_the_same_kind_choices_and_seed_give_the_same_round(mode, choices, seed):
    r = rounds.generate(mode, choices, seed)
    assert r == rounds.generate(mode, choices, seed)
    assert rounds.generate(r.mode, r.choices, r.seed, r.version) == r  # what the round carries rebuilds it
    assert r.mode in rounds.PLAYABLE


def test_another_version_of_a_template_is_refused_not_answered_differently():
    with pytest.raises(ValueError, match="counting is at version 1; version 2 is not kept"):
        rounds.generate(Mode.COUNTING, 4, 1, version=2)


def test_every_template_names_a_primary_skill_that_exists():
    from flashtap import content

    skills = content.load().skills
    for t in TEMPLATES.values():
        assert [s for s, role in t.skills if role is QRole.PRIMARY], t.mode
        assert all(s in skills for s, _ in t.skills), t.mode
    assert {t.mechanic for t in TEMPLATES.values()} == set(Mechanic)  # all eight mechanics have a template


@given(choice_counts, seeds)
def test_colours_never_offers_a_second_shape_of_the_named_colour(choices, seed):
    """The 0.1 generator drew distractors from every shape, so "Which one is red?" could show two red ones."""
    r = rounds.generate(Mode.COLOURS, choices, seed)
    colour = r.show.lower()
    colours = {t.id: t.colour for t in lexicon.words().shapes}
    assert [o.id for o in r.options if colours[o.id] == colour] == [r.answer]


@given(choice_counts, seeds)
def test_letters_has_one_word_with_the_sound_and_no_digraph_words(choices, seed):
    r = rounds.generate(Mode.LETTERS, choices, seed)
    by_id = {t.id: t for t in lexicon.words().everything}
    answer = by_id[r.answer]
    assert answer.letter == r.show
    assert [o.id for o in r.options if by_id[o.id].onset == answer.onset] == [r.answer]
    assert not {"chicken", "cheese"} & {o.id for o in r.options}  # "ch" is not the sound of C


def test_letters_offers_look_alike_and_near_sound_words_first():
    """D: a word starting with b or p (the letter turned over) or /t/ or /n/ (one sound feature away) is offered."""
    found = {"confusable_grapheme": 0, "phonological_neighbour": 0}
    for seed in range(300):
        r = rounds.generate(Mode.LETTERS, 4, seed)
        for o in r.options:
            if o.distractor in found:
                found[o.distractor] += 1
    assert all(found.values())


@given(seeds)
def test_counting_works_at_the_most_choices(seed):
    """The 0.1 generator looped forever above ten choices; eight is now the most, and it always fills."""
    r = rounds.generate(Mode.COUNTING, MAX_CHOICES, seed)
    n = int(r.answer[1:])
    assert 1 <= n <= 5
    assert len(r.show.split(" ")) == n
    assert all(1 <= int(o.picture) <= 10 for o in r.options)


def test_counting_offers_a_near_number_and_says_one_and_many_properly():
    seen: dict[int, str] = {}
    for seed in range(400):
        r = rounds.generate(Mode.COUNTING, 4, seed)
        right = next(o for o in r.options if o.correct)
        seen[int(right.picture)] = right.feedback
        n = int(right.picture)
        assert any(o.distractor == "near_number" and abs(int(o.picture) - n) == 1 for o in r.options)
    assert seen[1].startswith("Yes! There is 1 ")
    assert seen[3].startswith("Yes! There are 3 ")
    assert "sheeps" not in " ".join(rounds.generate(Mode.COUNTING, 4, s).prompt for s in range(400))


def test_matching_stays_in_one_category_and_uses_articles():
    for seed in range(200):
        r = rounds.generate(Mode.MATCHING, 4, seed)
        cats = {t.category for t in lexicon.words().everything if t.id in {o.id for o in r.options}}
        assert len(cats) == 1
        assert r.show == next(o.picture for o in r.options if o.correct)
    elephant = next(t for t in lexicon.words().animals if t.id == "elephant")
    assert elephant.a == "an elephant"


@given(choice_counts, seeds)
def test_missing_shows_one_gap_in_a_run_and_its_number_is_the_answer(choices, seed):
    r = rounds.generate(Mode.MISSING, choices, seed)
    run = r.show.split(" ")
    assert run.count("?") == 1
    i = run.index("?")
    known = [int(x) for x in run if x != "?"]
    start = known[0] - (1 if i == 0 else 0)
    assert [start + k for k in range(len(run))] == [int(x) if x != "?" else start + i for x in run]
    assert r.answer == f"n{start + i}"
    assert all(0 <= int(o.picture) <= 10 for o in r.options)


def test_missing_offers_the_reversal_of_six_and_nine():
    rs = [rounds.generate(Mode.MISSING, 4, s) for s in range(600)]
    six = [r for r in rs if r.answer == "n6"]
    assert six
    assert all(any(o.picture == "9" and o.distractor == "reversal" for o in r.options) for r in six)


@given(choice_counts, seeds)
def test_quick_look_hides_up_to_five_after_a_moment(choices, seed):
    r = rounds.generate(Mode.QUICK_LOOK, choices, seed)
    assert r.exposure_ms == 1500
    assert 1 <= len(r.show.split(" ")) <= 5
    assert r.answer == f"n{len(r.show.split(' '))}"
    assert r.say != r.prompt


@given(choice_counts, seeds)
def test_listen_never_offers_a_second_letter_for_the_same_sound_and_never_prints_the_word(choices, seed):
    r = rounds.generate(Mode.LISTEN, choices, seed)
    letters = {g.grapheme: g.phoneme for g in lexicon.words().letters}
    right = next(o for o in r.options if o.correct)
    assert [o.picture for o in r.options if letters[o.picture] == letters[right.picture]] == [right.picture]
    word = r.say.split(".")[0]
    assert word not in r.prompt.lower().replace(",", "").replace(".", "").split()
    assert r.show != word  # the picture, not the spelling


def test_listen_offers_k_for_neither_c_word_nor_c_for_a_k_sound():
    for seed in range(400):
        r = rounds.generate(Mode.LISTEN, 8, seed)
        pictures = {o.picture for o in r.options}
        assert not {"c", "k"} <= pictures or r.answer not in {"l_c", "l_k"}


@given(choice_counts, seeds)
def test_give_asks_for_fewer_than_the_pile_so_all_of_them_is_wrong(choices, seed):
    r = rounds.generate(Mode.GIVE, choices, seed)
    (basket,) = r.places
    assert 1 <= basket.holds <= 5
    assert len(r.pieces) >= basket.holds + 2
    assert set(basket.takes) == {p.id for p in r.pieces}
    assert not mx.arranged_right(r, {p.id: "basket" for p in r.pieces})
    assert mx.arranged_right(r, {p.id: "basket" for p in r.pieces[-basket.holds :]})
    assert f"Put {basket.holds} " in r.prompt


@given(choice_counts, seeds)
def test_order_wants_the_numbers_smallest_first(choices, seed):
    r = rounds.generate(Mode.ORDER, choices, seed)
    wanted = [int(s.takes[0][1:]) for s in r.places]
    assert wanted == sorted(wanted)
    assert len(set(wanted)) == len(wanted) == max(3, min(5, choices))
    assert [s.word for s in r.places][:3] == ["first", "second", "third"]


def test_capitals_brings_look_alike_letters_together():
    together = 0
    for seed in range(300):
        r = rounds.generate(Mode.CAPITALS, 4, seed)
        small = {p.picture for p in r.pieces}
        assert all(s.picture == s.takes[0].removeprefix("small_").upper() for s in r.places)
        together += bool({"b", "d"} <= small or {"m", "w"} <= small or {"n", "u"} <= small)
    assert together > 30


@given(choice_counts, seeds)
def test_sort_by_sound_puts_each_picture_with_one_letter_of_its_first_sound(choices, seed):
    r = rounds.generate(Mode.SORT_SOUNDS, choices, seed)
    by_id = {t.id: t for t in lexicon.words().everything}
    assert len(r.places) == 2
    assert len(r.pieces) == max(4, min(6, choices))
    sounds = set()
    for s in r.places:
        for k in s.takes:
            onset = by_id[k].onset
            assert onset is not None
            assert onset.grapheme == s.picture
            sounds.add(onset.phoneme)
        assert s.holds == len(s.takes) >= 2
    assert len(sounds) == 2


def test_mixed_plays_every_kind():
    played = {rounds.generate(Mode.MIXED, 4, s).mode for s in range(400)}
    assert played == set(rounds.PLAYABLE)


def test_an_unseeded_round_reports_the_seed_that_rebuilds_it():
    r = rounds.generate(Mode.SHAPES, 3)
    assert rounds.generate(Mode.SHAPES, 3, r.seed) == r


@pytest.mark.parametrize("choices", [1, 9])
def test_choices_outside_the_range_are_refused(choices):
    with pytest.raises(ValueError, match="choices must be between 2 and 8"):
        rounds.generate(Mode.MATCHING, choices, 1)


PRIMARY = [SkillRole(skill="x", role=QRole.PRIMARY)]


def _choose(options: list[Option], answer: str = "a", **kw: object) -> Round:
    fields = {"mechanic": Mechanic.SELECT_ONE, "skills": PRIMARY, "options": options, "answer": answer} | kw
    return Round.model_validate(
        {
            "mode": Mode.MATCHING,
            "version": 1,
            "content": {},
            "choices": 2,
            "seed": 1,
            "prompt": "p",
            "say": "p",
            **fields,
        }
    )


def _opt(id_: str, correct: bool, picture: str | None = None, distractor: str = "random") -> Option:
    return Option(id=id_, picture=picture or id_, word=id_, correct=correct, feedback="", distractor=distractor)


@pytest.mark.parametrize(
    ("options", "answer", "message"),
    [
        ([_opt("a", True), _opt("b", True)], "a", "2 right answers"),
        ([_opt("a", False), _opt("b", False)], "a", "0 right answers"),
        ([_opt("a", True), _opt("b", False)], "b", "is not the right option"),
        ([_opt("a", True), _opt("b", False, picture="a")], "a", "repeated options"),
        ([_opt("a", True)], "a", "only 1 options"),
        ([_opt("a", True), _opt("b", False, distractor="")], "a", "no distractor named"),
    ],
)
def test_check_refuses_broken_choose_rounds(options, answer, message):
    with pytest.raises(InvalidRound, match=message):
        mx.check(_choose(options, answer))


def test_check_refuses_a_round_without_a_primary_skill_and_misplaced_exposure():
    ok = [_opt("a", True), _opt("b", False)]
    with pytest.raises(InvalidRound, match="no primary skill"):
        mx.check(_choose(ok, skills=[SkillRole(skill="x", role=QRole.CONFOUND)]))
    with pytest.raises(InvalidRound, match="only a brief exposure"):
        mx.check(_choose(ok, exposure_ms=100))
    with pytest.raises(InvalidRound, match="needs something to show"):
        mx.check(_choose(ok, mechanic=Mechanic.BRIEF_EXPOSURE))
    with pytest.raises(InvalidRound, match="no pieces or places"):
        mx.check(_choose(ok, pieces=[Piece(id="p", picture="p", word="p")]))


def _place(pieces: list[Piece], places: list[Place], **kw: object) -> Round:
    fields = {"mechanic": Mechanic.SORT, "skills": PRIMARY, "pieces": pieces, "places": places, "done_feedback": "Yes!"}
    return Round.model_validate(
        {
            "mode": Mode.SORT_SOUNDS,
            "version": 1,
            "content": {},
            "choices": 2,
            "seed": 1,
            "prompt": "p",
            "say": "p",
            **(fields | kw),
        }
    )


def _pc(id_: str, picture: str | None = None) -> Piece:
    return Piece(id=id_, picture=picture or id_, word=picture or id_)


def _pl(id_: str, takes: list[str], holds: int = 1, picture: str | None = None) -> Place:
    return Place(id=id_, picture=picture or id_, word=id_, takes=takes, holds=holds)


@pytest.mark.parametrize(
    ("pieces", "places", "message"),
    [
        ([_pc("a"), _pc("a")], [_pl("x", ["a"])], "repeated ids"),
        ([_pc("a")], [_pl("x", ["a"])], "too few pieces or places"),
        ([_pc("a"), _pc("b")], [_pl("x", ["c"])], "takes c, which is not a piece"),
        ([_pc("a"), _pc("b")], [_pl("x", ["a"]), _pl("y", ["a"])], "a belongs in x and y"),
        ([_pc("a"), _pc("b")], [_pl("x", ["a"], holds=2)], "must hold 2 but takes 1"),
        ([_pc("a", "🍎"), _pc("b", "🍎")], [_pl("x", ["a"]), _pl("y", ["b"])], "look the same belong in different"),
        ([_pc("a"), _pc("b")], [_pl("x", ["a"], picture="s"), _pl("x2", ["b"], picture="s")], None),
    ],
)
def test_check_refuses_ambiguous_place_rounds(pieces, places, message):
    r = _place(pieces, places)
    if message is None:  # two places with the same picture but different words are told apart by their words
        mx.check(r)
        return
    with pytest.raises(InvalidRound, match=message):
        mx.check(r)


def test_check_refuses_a_place_round_with_options_twin_places_or_no_words_for_done():
    pieces, places = [_pc("a"), _pc("b")], [_pl("x", ["a"]), _pl("y", ["b"])]
    with pytest.raises(InvalidRound, match="has no options"):
        mx.check(_place(pieces, places, answer="a"))
    twins = [
        Place(id="x", picture="s", word="s", takes=["a"], holds=1),
        Place(id="y", picture="s", word="s", takes=["b"], holds=1),
    ]
    with pytest.raises(InvalidRound, match="two places look the same"):
        mx.check(_place(pieces, twins))
    with pytest.raises(InvalidRound, match="no words for a right arrangement"):
        mx.check(_place(pieces, places, done_feedback=""))


def test_arranged_right_wants_each_place_full_of_what_it_takes():
    r = _place([_pc("a"), _pc("b"), _pc("c")], [_pl("x", ["a", "b"], holds=2), _pl("y", ["c"])])
    assert mx.arranged_right(r, {"a": "x", "b": "x", "c": "y"})
    assert not mx.arranged_right(r, {"a": "x", "c": "y"})  # x holds one too few
    assert not mx.arranged_right(r, {"a": "x", "b": "y", "c": "x"})  # wrong pieces


@pytest.mark.parametrize(
    ("tries", "mode", "allowed"),
    [(0, Mode.COUNTING, None), (1, Mode.COUNTING, 1), (2, Mode.COUNTING, 2), (5, Mode.COUNTING, 3), (3, Mode.GIVE, 3)],
)
def test_tries_allowed_never_reaches_the_last_option_and_counts_checks_on_place_rounds(tries, mode, allowed):
    assert rounds.tries_allowed(tries, rounds.generate(mode, 4, 1)) == allowed


def test_the_place_and_choose_families_cover_the_mechanics_once():
    assert set(Mechanic) == CHOOSE | PLACE
    assert not CHOOSE & PLACE


def test_a_round_names_the_packs_it_drew_from_and_rebuilds_only_from_them() -> None:
    r = rounds.generate(Mode.LETTERS, 4, 7)
    # The words and phonics behind the pictures and letters, and the packs of the skills it names; never a curriculum.
    assert set(r.content) == {"words", "phonics.letters_and_sounds", "literacy.early", "language"}
    assert rounds.generate(Mode.LETTERS, 4, 7, r.version, r.content) == r
    with pytest.raises(ValueError, match=r"made from .*words@0.*not kept"):
        rounds.generate(Mode.LETTERS, 4, 7, r.version, {**r.content, "words": 0})
    mixed = rounds.generate(Mode.MIXED, 4, 3)
    assert mixed.content == rounds.content_of(mixed.mode)  # the kind played, not Mixed


# Steps of difficulty (0.11.0): every step of every template, a few hundred seeds each, one unmistakable answer, the
# step's own number of choices, and the number asked about kept within the step's top.
def _asked(r: Round) -> int:
    """The number a number round is about: the right numeral, how many go in the basket, or the largest to order."""
    if r.mechanic is Mechanic.GIVE_N:
        return r.places[0].holds
    if r.mechanic is Mechanic.SEQUENCE:
        return max(int(p.word) for p in r.pieces)
    return int(next(o.word for o in r.options if o.correct))


@pytest.mark.parametrize("mode", rounds.PLAYABLE)
def test_every_step_of_every_template_gives_one_answer_at_its_own_size(mode):
    t = TEMPLATES[mode]
    assert t.levels, "every template has steps"
    for level, step in enumerate(t.levels):
        assert MIN_CHOICES <= step.choices <= MAX_CHOICES
        assert step.says
        for seed in range(300):
            r = rounds.at_level(mode, level, seed)
            assert (r.level, r.choices) == (level, step.choices)
            assert rounds.generate(r.mode, r.choices, r.seed, r.version, r.content, r.level) == r  # it rebuilds
            if r.mechanic in CHOOSE:
                assert len(r.options) == step.choices
                assert [o.id for o in r.options if o.correct] == [r.answer]
            if step.top is not None:
                assert _asked(r) <= step.top


def test_number_steps_lay_out_what_they_say():
    for seed in range(300):
        count = rounds.at_level(Mode.COUNTING, 0, seed)  # up to 3 pictures, among the numerals to 5
        assert len(count.show.split()) <= 3
        assert all(1 <= int(o.word) <= 5 for o in count.options)
        give = rounds.at_level(Mode.GIVE, 3, seed)  # up to 10 asked for, always more in the pile
        assert len(give.pieces) > give.places[0].holds
        order = rounds.at_level(Mode.ORDER, 3, seed)
        assert len(order.pieces) == 5
        assert all(0 <= int(p.word) <= 20 for p in order.pieces)
        missing = rounds.at_level(Mode.MISSING, 0, seed)
        assert all(0 <= int(o.word) <= 5 for o in missing.options)
    assert max(rounds.at_level(Mode.GIVE, 3, s).places[0].holds for s in range(300)) == 10  # the top is reached


def test_a_round_with_no_step_is_built_as_before_steps_existed():
    # A step is a new part of the rebuild key, so a round made before 0.11.0 (no step) rebuilds unchanged: the
    # numbers come from the kinds' fixed ranges, whatever the grown-up's choices.
    for seed in range(200):
        r = rounds.generate(Mode.COUNTING, 8, seed)
        assert r.level is None
        assert len(r.show.split()) <= 5
        assert all(1 <= int(o.word) <= 10 for o in r.options)


def test_a_step_out_of_range_or_with_other_choices_is_refused():
    with pytest.raises(ValueError, match="counting has steps 0 to 3, not 4"):
        rounds.at_level(Mode.COUNTING, 4, 1)
    with pytest.raises(ValueError, match="counting has steps 0 to 3, not 9"):
        rounds.generate(Mode.COUNTING, 4, 1, level=9)
    with pytest.raises(ValueError, match="counting step 0 lays out 3, not 4"):
        rounds.generate(Mode.COUNTING, 4, 1, level=0)
    with pytest.raises(ValueError, match="not to Mixed"):
        rounds.generate(Mode.MIXED, 4, 1, level=0)
    with pytest.raises(ValueError, match="not to Mixed"):
        rounds.at_level(Mode.MIXED, 0, 1)
