# Unit tests

Shared commands, layout, hermetic setup and file-ownership rules are in [`tests/README.md`](../README.md); read that first. This file is owned by unit-test work.

Fast and isolated: synthetic data and fakes; no external services, no network. `pytest tests/unit --cov` is what CI gates on (`fail_under` in `pyproject.toml`).

## Where things are tested

| Module | Tests | Coverage | Status | Notes |
| --- | --- | --- | --- | --- |
| `rounds.py` | `test_rounds.py` | 100% | done | hypothesis over every mode, choice count and seed: exactly one right answer, no repeats, same seed same round; `check` refusals; `tries_allowed` |
| `lexicon.py` | `test_lexicon.py` | 100% | done | ids unique, plurals and articles, Letters excludes words without a plain first sound |
| `settings.py` | `test_settings.py` | 100% | done | mode/choices/tries defaults, ranges, bad stored values fall back |
| `cli.py` | `test_cli.py` | 100% | done | doctor, round (text and JSON, bad choices), set, serve delegation |
| `server/app.py` | `test_server.py` | 100% | done | landing page, modes, round (seeded, validation, tries from settings) |
