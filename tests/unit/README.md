# Unit tests

Shared commands, layout, hermetic setup and file-ownership rules are in [`tests/README.md`](../README.md); read that first. This file is owned by unit-test work.

Fast and isolated: synthetic data and fakes; no external services, no network. `pytest tests/unit --cov` is what CI gates on (`fail_under` in `pyproject.toml`).

## Where things are tested

| Module | Tests | Coverage | Status | Notes |
| --- | --- | --- | --- | --- |
| `rounds.py`, `mechanics.py`, `kinds/` | `test_rounds.py` | 100% (two defensive raises aside) | done | 1,000 seeds of every template (the plan's exit for the mechanics); hypothesis over every kind, choice count and seed: same seed same round, and a round's own (kind, version, choices, seed) rebuild it; per-kind rules (one colour, one first sound, a run with one gap, a quick look hides, Listen offers no second letter for the sound, give asks fewer than the pile, order smallest first, look-alike capitals together, sort by one sound); `check` refusals for both families; `arranged_right`; `tries_allowed` |
| `distractors.py` | `test_distractors.py` | 100% | done | near numbers nearest first, reversals, confusable letters, phonological neighbours, `fill` order and exclusions |
| `lexicon.py` | `test_lexicon.py` | 100% | done | ids unique, plurals and articles, Letters excludes words without a plain first sound |
| `content/` | `test_content.py` | 99% | done | shipped packs pass; every EYFS maths and literacy goal mapped or set aside; each check rule refuses its mistake (copies of the real packs plus one bad pack in `tmp_path`); a later-stage skill needs no schema change; GPC resolution, decodability, summary rows |
| (repository) | `test_privacy.py` | n/a | done | no file states a person's age or birth date (AGENTS.md rule 8) |
| `settings.py` | `test_settings.py` | 100% | done | mode/choices/tries defaults, ranges, bad stored values fall back |
| `cli.py` | `test_cli.py` | 100% | done | doctor, round (text and JSON, bad choices), content check (ok, problems) and list (text, JSON), set, serve delegation |
| `server/app.py` | `test_server.py` | 100% | done | landing page, modes, round (seeded, validation, tries from settings), content |
