"""Rule 8 of AGENTS.md: a public repository for a private app holds nothing that identifies a person.

A word list cannot catch a name, so this guards the shapes an identifying detail about a learner usually takes (an
age, a birth date, a year group tied to a person); review guards the rest.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", "node_modules", "static", "baselines", "storybook-static", "dist", "output", "coverage"}
TEXT = {".py", ".md", ".mdx", ".ts", ".tsx", ".css", ".html", ".toml", ".yml", ".yaml", ".json", ".service", ".txt"}
SKIP_FILES = {"package-lock.json", "uv.lock", "CHANGELOG.md", "test_privacy.py"}

IDENTIFYING = re.compile(
    r"\b\d{1,2}[- ]years?[- ]old\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)[- ]years?[- ]old\b"
    r"|\bdate of birth\b|\bbirthday\b|\bdob\s*[:=]",
    re.IGNORECASE,
)


def _files() -> list[Path]:
    return [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix in TEXT
        and p.name not in SKIP_FILES
        and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
    ]


def test_the_scan_reads_the_repository() -> None:
    names = {p.relative_to(ROOT).as_posix() for p in _files()}
    assert {"AGENTS.md", "src/flashtap/rounds.py", "web/src/screens/PlayScreen.tsx"} <= names


def test_no_file_states_an_age_or_birth_date() -> None:
    found = [
        f"{p.relative_to(ROOT)}:{n}: {line.strip()}"
        for p in _files()
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if IDENTIFYING.search(line)
    ]
    assert found == []


def test_the_pattern_catches_the_usual_shapes() -> None:
    for text in ("a three-year-old", "she is 4 years old", "DOB: 2021-01-01", "her birthday", "date of birth"):
        assert IDENTIFYING.search(text), text
    for text in ("five kinds of round", "Year 2 skills", "2026-11-23"):
        assert not IDENTIFYING.search(text), text
