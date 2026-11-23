# Unit tests

Shared commands, layout, hermetic setup and file-ownership rules are in [`tests/README.md`](../README.md); read that first. This file is owned by unit-test work.

Fast and isolated: synthetic data and fakes; no external services, no network. `pytest tests/unit --cov` is what CI gates on (`fail_under` in `pyproject.toml`).

## Where things are tested

| Module | Tests | Coverage | Status | Notes |
| --- | --- | --- | --- | --- |
| `rounds.py` | `test_rounds.py` | 100% | done | hypothesis over every mode, choice count and seed: exactly one right answer, no repeats, same seed same round; `check` refusals; `tries_allowed` |
| `lexicon.py` | `test_lexicon.py` | 100% | done | ids unique, plurals and articles, Letters excludes words without a plain first sound |
| `content/` | `test_content.py` | 99% | done | shipped packs pass; every EYFS maths and literacy goal mapped or set aside; each check rule refuses its mistake (copies of the real packs plus one bad pack in `tmp_path`); a later-stage skill needs no schema change; GPC resolution, decodability, summary rows |
| (repository) | `test_privacy.py` | n/a | done | no file states a person's age or birth date (AGENTS.md rule 8) |
| `settings.py` | `test_settings.py` | 100% | done | mode/choices/tries defaults, ranges, bad stored values fall back |
| `cli.py` | `test_cli.py` | 100% | done | doctor, round (text and JSON, bad choices), content check (ok, problems) and list (text, JSON), set, serve delegation |
| `server/app.py` | `test_server.py` | 100% | done | landing page, modes, round (seeded, validation, tries from settings), content |
