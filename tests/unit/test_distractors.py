import random

import pytest

from flashtap import distractors as dx


def test_near_numbers_come_nearest_first_with_ties_in_seeded_order():
    a = dx.near_numbers(5, 1, 10, random.Random(1))
    assert sorted(a[:2]) == [4, 6]
    assert sorted(a[2:4]) == [3, 7]
    assert 5 not in a
    assert len(a) == 9
    sides = {tuple(dx.near_numbers(5, 1, 10, random.Random(s))[:1]) for s in range(20)}
    assert sides == {(4,), (6,)}  # neither side is always first


@pytest.mark.parametrize(("n", "flipped"), [(6, 9), (9, 6), (12, 21), (21, 12), (11, None), (10, None), (3, None)])
def test_reversal_turns_six_and_nine_and_swaps_two_digits(n, flipped):
    assert dx.reversal(n) == flipped


@pytest.mark.parametrize(("g", "look"), [("b", ["d", "p", "q"]), ("m", ["w"]), ("u", ["n"]), ("s", [])])
def test_confusable_graphemes(g, look):
    assert dx.confusable_graphemes(g) == look


@pytest.mark.parametrize(
    ("p", "near"),
    [
        ("b", ["p", "d", "ɡ", "m", "w"]),  # noqa: RUF001 (IPA)
        ("s", ["t", "z", "f", "h"]),
        ("æ", ["e", "ʌ"]),
        ("ʃ", []),
    ],
)
def test_phonological_neighbours_differ_in_one_feature(p, near):
    assert sorted(dx.phonological_neighbours(p)) == sorted(near)


def test_fill_takes_preferred_first_then_random_and_never_an_excluded_value():
    rng = random.Random(3)
    out = dx.fill(rng, 4, [(2, "near"), (2, "again"), (9, "near")], list(range(10)), {5, 9})
    assert out[0] == (2, "near")
    assert [why for _, why in out[1:]] == ["random"] * 3
    assert len({v for v, _ in out}) == 4
    assert not {5, 9} & {v for v, _ in out}
    assert sorted(dx.fill(rng, 5, [], [1, 2], set())) == [(1, "random"), (2, "random")]  # as many as the pool has
