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
| (repository) | `test_privacy.py` | n/a | done | the repository's `[tool.strata-public-check] deny` patterns catch an age or a birth date, and no file git would commit matches them (AGENTS.md rule 8) |
| `settings.py` | `test_settings.py` | 100% | done | mode/choices/tries defaults, ranges, bad stored values fall back |
| `cli.py` | `test_cli.py` | 100% | done | doctor, round (text and JSON, bad choices), content check (ok, problems) and list (text, JSON), learners list and rebuild (exact, and a changed export), set, serve delegation |
| `server/app.py` | `test_server.py` | 100% | done | landing page, modes, round (seeded, validation, tries from settings), content; the learner routes over HTTP (add, taken nickname, rename, record, resend, conflicting event, refused version, unknown learner, bad id, profile, evidence, strike, export header, delete) |
| `learners/` | `test_learners.py`, `test_database.py` | 100% | done | on a real migrated SQLite (strata_python.db's `db_session`): learners and nicknames, delete removes every row, the server judges first answers (tap and arrangement), idempotent events and refused rewrites, sessions span their attempts, impossible attempts refused, tombstones; the evidence rules (held back while a confound is unseen, secondary credited only when right); BKT and the rule by hand; the reporting-state ladder; **replay: 60 attempts exported and rebuilt exactly, also when sent in another order**, and a changed log caught; where the records go with no database configured; `test_database.py` is strata_python.db's schema-matches-models and migrations up, down and up |
