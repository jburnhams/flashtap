"""Rule 8 of AGENTS.md: a public repository for a private app holds nothing that identifies a person.

A word list cannot catch a name, so the repository's `[tool.strata-public-check] deny` patterns (pyproject.toml) guard
the shapes an identifying detail about a learner usually takes (an age, a birth date); strata-python's
`strata-public-check .` applies them to every file git would commit, web source included, in CI. Review guards the
rest. These tests keep the patterns honest and the tree clean between CI runs.
"""

import re
from pathlib import Path

import pytest
from strata_python import public_check

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def deny() -> list[tuple[str, re.Pattern[str]]]:
    return public_check.config_deny(ROOT)


def caught(deny: list[tuple[str, re.Pattern[str]]], text: str) -> bool:
    return any(p.search(text) for _, p in deny)


def test_the_patterns_catch_the_usual_shapes(deny) -> None:
    for text in ("a three-year-old", "she is 4 years old", "DOB: 2021-01-01", "her birthday", "date of birth"):
        assert caught(deny, text), text
    for text in ("five kinds of round", "Year 2 skills", "2026-11-23"):
        assert not caught(deny, text), text


def test_the_repository_holds_none_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    # What CI runs, here too, so a story or fixture that names an age fails before it is pushed.
    monkeypatch.chdir(ROOT)
    findings = public_check.scan(
        [ROOT], exclude=public_check.config_excludes(ROOT), repo=public_check.config_deny(ROOT)
    )
    assert [str(f) for f in findings] == []
