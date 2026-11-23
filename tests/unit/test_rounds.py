import pytest
from hypothesis import given
from hypothesis import strategies as st

from flashtap import lexicon, rounds
from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, InvalidRound, Mode, Option, Round

modes = st.sampled_from(list(Mode))
choice_counts = st.integers(MIN_CHOICES, MAX_CHOICES)
seeds = st.integers(0, rounds.SEED_LIMIT - 1)


@given(modes, choice_counts, seeds)
def test_every_round_has_one_right_answer_and_the_number_of_choices_asked_for(mode, choices, seed):
    r = rounds.generate(mode, choices, seed)  # generate() runs check(); this restates its rules from the outside
    assert [o.id for o in r.options if o.correct] == [r.answer]
    assert len(r.options) == choices
    assert len({o.picture for o in r.options}) == choices
    assert r.mode in rounds.PLAYABLE
    assert r.seed == seed


@given(modes, choice_counts, seeds)
def test_the_same_seed_gives_the_same_round(mode, choices, seed):
    assert rounds.generate(mode, choices, seed) == rounds.generate(mode, choices, seed)


@given(choice_counts, seeds)
def test_colours_never_offers_a_second_shape_of_the_named_colour(choices, seed):
    """The old generator drew distractors from every shape, so "Which one is red?" could show two red ones."""
    r = rounds.generate(Mode.COLOURS, choices, seed)
    colour = r.show.lower()
    colours = {t.id: t.colour for t in lexicon.words().shapes}
    assert [o.id for o in r.options if colours[o.id] == colour] == [r.answer]


@given(choice_counts, seeds)
def test_letters_has_one_word_with_the_letter_and_no_digraph_words(choices, seed):
    r = rounds.generate(Mode.LETTERS, choices, seed)
    by_id = {t.id: t for t in lexicon.words().animals + lexicon.words().food}
    assert [o.id for o in r.options if by_id[o.id].letter == r.show] == [r.answer]
    assert not {"chicken", "cheese"} & {o.id for o in r.options}  # "ch" is not the sound of C


@given(seeds)
def test_counting_works_at_the_most_choices(seed):
    """The old generator looped forever above ten choices; eight is now the most, and it always fills."""
    r = rounds.generate(Mode.COUNTING, MAX_CHOICES, seed)
    n = int(r.answer[1:])
    assert 1 <= n <= rounds.COUNT_MOST
    assert len(r.show.split(" ")) == n
    assert all(1 <= int(o.picture) <= 10 for o in r.options)


def test_counting_says_one_and_many_properly():
    seen: dict[int, str] = {}
    for seed in range(400):
        r = rounds.generate(Mode.COUNTING, 4, seed)
        right = next(o for o in r.options if o.correct)
        seen[int(right.picture)] = right.feedback
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


def test_mixed_plays_every_mode_and_is_reproducible():
    played = {rounds.generate(Mode.MIXED, 4, s).mode for s in range(100)}
    assert played == set(rounds.PLAYABLE)


def test_an_unseeded_round_reports_the_seed_that_rebuilds_it():
    r = rounds.generate(Mode.SHAPES, 3)
    assert rounds.generate(Mode.SHAPES, 3, r.seed) == r


@pytest.mark.parametrize("choices", [1, 9])
def test_choices_outside_the_range_are_refused(choices):
    with pytest.raises(ValueError, match="choices must be between 2 and 8"):
        rounds.generate(Mode.MATCHING, choices, 1)


def _round(options: list[Option], answer: str = "a") -> Round:
    return Round(mode=Mode.MATCHING, seed=1, prompt="p", show="s", options=options, answer=answer)


def _opt(id_: str, correct: bool, picture: str | None = None) -> Option:
    return Option(id=id_, picture=picture or id_, word=id_, correct=correct, feedback="")


@pytest.mark.parametrize(
    ("options", "answer", "message"),
    [
        ([_opt("a", True), _opt("b", True)], "a", "2 right answers"),
        ([_opt("a", False), _opt("b", False)], "a", "0 right answers"),
        ([_opt("a", True), _opt("b", False)], "b", "is not the right option"),
        ([_opt("a", True), _opt("b", False, picture="a")], "a", "repeated options"),
        ([_opt("a", True)], "a", "only 1 options"),
    ],
)
def test_check_refuses_broken_rounds(options, answer, message):
    with pytest.raises(InvalidRound, match=message):
        rounds.check(_round(options, answer))


@pytest.mark.parametrize(
    ("tries", "options", "allowed"),
    [(0, 4, None), (1, 4, 1), (2, 4, 2), (5, 4, 3), (3, 2, 1)],
)
def test_tries_allowed_never_reaches_the_last_option(tries, options, allowed):
    assert rounds.tries_allowed(tries, options) == allowed
