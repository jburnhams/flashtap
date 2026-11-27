"""Talk (flashtap.talk): what a written line must be to be kept, the pools filled by the write role (passed in here: the
true external edge; tests/unit/test_jobs.py runs it through the `fake_models` service over HTTP), the nickname filled
in on the server and never sent, and every line said handed to the voice build."""

from pathlib import Path
from typing import Any

import pytest

from flashtap import rounds, talk, voice


@pytest.fixture
def store(tmp_path: Path) -> talk.Store:
    return talk.Store(tmp_path / "voice")


class Writer:
    """The write role's answer for each moment: `lines`, or a function of the moment's prompt."""

    def __init__(self, lines: list[str] | None = None, fail: str | None = None) -> None:
        self.lines = lines or []
        self.fail = fail
        self.prompts: list[str] = []
        self.params: list[dict[str, Any]] = []

    def __call__(self, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.params.append(params)
        if self.fail and self.fail in prompt:
            raise RuntimeError("the job failed")
        return {"text": "", "json": {"lines": self.lines}, "model": "claude-sonnet-5-5-api"}


@pytest.mark.parametrize(
    ("key", "line", "why"),
    [
        ("right", "Brilliant, {name}!", None),
        ("right", "You got it!", None),
        ("retry", "Have another look.", None),
        ("pick", "Your turn to choose. Which one next?", None),
        ("break", "Fancy a rest?", None),
        ("intro.counting", "Now for some counting.", None),
        ("right", "There are 5!", "numbers would state an answer"),
        ("retry", "That was wrong, try again.", "the word 'wrong'"),
        ("right", "Good girl!", "the word 'girl'"),
        ("right", "Well done, he did it!", "the word 'he'"),
        ("pick", "Ready? Which one next?", "a question inside it"),
        ("start", "Ready to play?", "a question where none is asked"),
        ("break", "Time to rest.", "not a question"),
        ("right", "Yes {name}, {name}!", "the name more than once"),
        ("right", "Well done, {child}!", "a placeholder other than {name}"),
        ("right", "Well done 🎉!", "a character other than letters"),
        ("right", "Well done", "no full stop"),
        ("right", "You found it and that is really very good work today!", "more than 9 words"),
        ("right", "", "not 1 to 60 characters"),
        ("nope", "Hello.", "no moment nope"),
    ],
)
def test_a_written_line_is_kept_only_if_it_fits_its_moment(key: str, line: str, why: str | None):
    got = talk.check(key, line)
    if why is None:
        assert got is None
    else:
        assert got is not None
        assert why in got


def test_every_kind_of_round_has_an_intro_and_every_moment_a_brief():
    m = talk.moments()
    assert {talk.intro_key(k) for k in rounds.PLAYABLE} <= set(m)
    assert set(talk.MOMENTS) <= set(m)
    assert "Counting" in m["intro.counting"].brief
    for key, moment in m.items():  # the fixed lines pass their own checks
        assert not moment.fixed or talk.check(key, moment.fixed) is None, key


def test_write_fills_each_pool_with_the_lines_that_pass_and_never_sends_a_name(store: talk.Store):
    w = Writer(["Brilliant!", "Brilliant!", "Good girl!", "Yes!", "Well done, {name}!", "You got it."])
    r = talk.write(store, ["right"], ask=w)
    assert r.added == {"right": 3}
    assert [x.text for x in store.read().lines["right"]] == ["Brilliant!", "Well done, {name}!", "You got it."]
    assert store.read().lines["right"][0].model == "claude-sonnet-5-5-api"
    assert [x.split(":")[0] for x in r.refused["right"]] == ["Brilliant!", "Good girl!", "Yes!"]  # again, banned, fixed
    assert w.params[0]["schema"] == talk.SCHEMA
    assert "{name}" in w.params[0]["system"]
    assert "Write 10 lines." in w.prompts[0]  # what is still needed, and two over for those refused
    # the next call says what is there already, so it is not written again
    talk.write(store, ["right"], ask=w)
    assert "Brilliant!; Well done, {name}!; You got it.; Yes!" in w.prompts[1]


def test_a_full_pool_is_not_asked_for_and_a_pool_never_grows_past_its_size(store: talk.Store):
    lines = [f"Well done {w}." for w in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]]
    r = talk.write(store, ["retry"], ask=Writer(lines))
    assert r.added == {"retry": talk.POOL}
    w = Writer(lines)
    assert talk.write(store, ["retry"], ask=w).full == ["retry"]
    assert w.prompts == []


def test_a_moment_that_fails_is_named_and_the_rest_are_written(store: talk.Store):
    r = talk.write(store, ["right", "retry"], ask=Writer(["Have a go."], fail="right answer"))
    assert set(r.failed) == {"right"}
    assert r.added == {"retry": 1}
    bad = talk.write(store, ["pick"], ask=lambda _p, _q: {"json": {"words": []}})
    assert "lines" in bad.failed["pick"]


def test_write_stops_between_moments_when_asked(store: talk.Store):
    r = talk.write(store, ["right", "retry"], ask=Writer(["Super."]), stop=lambda: True)
    assert r.left == ["right", "retry"]
    assert store.read().lines == {}


def test_a_struck_line_is_taken_out_and_never_written_again(store: talk.Store):
    talk.write(store, ["right"], ask=Writer(["Super.", "Lovely, {name}!"]))
    assert store.strike("Super.") == 1
    assert [x.text for x in store.read().lines["right"]] == ["Lovely, {name}!"]
    assert store.strike("Never said.") == 0
    talk.write(store, ["right"], ask=Writer(["Super.", "Never said."]))
    assert [x.text for x in store.read().lines["right"]] == ["Lovely, {name}!"]


def test_pools_fill_in_the_nickname_and_leave_out_name_lines_without_one(store: talk.Store):
    talk.write(store, ["right"], ask=Writer(["Super.", "Lovely, {name}!"]))
    book = store.read()
    assert talk.pools(book, "Fox").lines["right"] == ["Yes!", "Super.", "Lovely, Fox!"]
    assert talk.pools(book, None).lines["right"] == ["Yes!", "Super."]
    assert talk.pools(book, "🦊").lines["right"] == ["Yes!", "Super."]  # not a name a line says well
    assert talk.pools(book, "Fox").lines["intro.counting"] == []  # nothing written, and no fixed intro
    assert talk.speakable("  Little   Bear ") == "Little Bear"
    assert talk.speakable("R2") is None


def test_every_line_said_for_each_learner_goes_to_the_voice_build(store: talk.Store, monkeypatch: pytest.MonkeyPatch):
    talk.write(store, ["right", "start"], ask=Writer(["Lovely, {name}!", "Hello, {name}. Let's go."]))
    said = talk.said(store.read(), ["Fox", "Owl"])
    assert {"Yes!", "Lovely, Fox!", "Lovely, Owl!", "Let's play.", "Hello, Fox. Let's go."} <= set(said)
    monkeypatch.setattr(voice, "home", lambda: store.root)
    wanted = voice.wanted(["Fox"])
    assert wanted[: len(voice.lines())] == voice.lines()  # the rounds' lines first, as before
    assert {"Lovely, Fox!", "Hello, Fox.", "Let's go.", "Good try."} <= set(wanted)  # cut as the web app cuts them
    assert "Lovely, Owl!" not in wanted
