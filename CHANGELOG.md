# Changelog

Newest first, grouped by day. One entry per change, in the same commit or PR as the change.

## 2026-11-22

**Flashtap 0.2.0: a Python web app on strata-python and strata-react (branch `claude/project-thread-fmqqff`)**
Jonathan asked to change Flashtap from a React/TypeScript npm library into a Python web app on strata-python and strata-react, then to plan growing it toward his early-years adaptive learning spec. This is PR 1 of that plan (`docs/implementation-plan.md`): the same five kinds of round, now owned by the server, with the old generators' bugs fixed. The entries below this one are python-app-template's history, which Flashtap was built from.

- `src/`, `tests/`, `docs/` (demo site), `package.json`, `package-lock.json`, `tsconfig*.json`, `vite.config.ts`, `vitest*.config.ts`, `playwright.config.ts`, `.github/workflows/{browser-tests,deploy-docs,integration-tests,node.js,npm-publish,release}.yml`: **removed** (the npm library and its CI).
- python-app-template's files copied in, with `src/app` renamed `src/flashtap`, `app`/`app.cmd` renamed `flashtap`/`flashtap.cmd`, port 8361, and the sample greetings, log and status page removed (`greet.py`, `system.py`, their screens, stories and tests). `upgrade-strata-python.yml` removed: strata-python now comes from PyPI (`strata-python>=0.2,<0.3`).
- `pyproject.toml`, `uv.lock`: package `flashtap` 0.2.0, MIT, `hypothesis` for property tests, `FLASHTAP_*` environment.
- `src/flashtap/lexicon.py`: **new**. Every word with its plural and article written down ("sheep", "an elephant", "some grapes") and its first sound for Letters (chicken and cheese left out: "What starts with C?" must not mix two sounds); aeroplane in UK English.
- `src/flashtap/rounds.py`: **new**. Seeded rounds (same mode, choices and seed give the same round) checked for exactly one right answer, no repeats and enough choices. Corrections to the old generators: Colours offered two red shapes for "Which one is red?", Counting looped forever above ten choices, tiles printed their own names (Letters and Colours became reading tasks), and plurals and articles were built by string templates.
- `src/flashtap/settings.py`, `src/flashtap/server/app.py`, `src/flashtap/server/landing.html`, `src/flashtap/cli.py`: **new**. Settings mode, choices (2 to 8) and tries (0 for no limit); `GET /api/modes`, `GET /api/round`; `flashtap round`.
- `web/src/`: **new** Play screen (prompt said aloud, en-GB voice first; a wrong tap greys the tile and says what it was; the right tap or running out of tries shows the answer and Next; no score) and Settings screen; `api.ts`, `play.ts`, `speech.ts`, mocks, routes. `styles/play.css` is the tile layout's stand-in until strata-react has a tap-tile component. Fonts Andika and Twemoji (COLR; Noto's SVG emoji font renders blank in Chromium); palette regenerated from blackboard green and pencil yellow.
- `web/tests/`, `web/stories/`, `web/strata-visual.config.ts`: tests and stories for both screens; coverage floors 100. Visual baselines are not committed: they are written by the *Update visual baselines* workflow on the CI runner.
- `tests/`: unit and integration suites for the above; `fail_under` 95.
- `README.md`, `AGENTS.md`, `NOTICE`, `docs/{overview,implementation-plan,progress,deploying}.md`, `deploy/flashtap.service`, `tests/**/README.md`, `web/tests/README.md`, `docs/prompts/`: describe Flashtap. `AGENTS.md`: what Strata lacks is now added to strata-react rather than raised as an issue (Jonathan, 2026-11-22).

## 2026-11-09

**Regenerate visual baselines on the CI runner (branch `claude/project-thread-iw7199`)**
Jonathan wants every dependency kept current, including Dependabot's playwright and lucide-react bumps. Those change the Chromium or the icons behind every screenshot, and a laptop cannot reproduce the CI Chromium, so the baselines are now written by a manual workflow.

- `.github/workflows/update-visual-baselines.yml`: **new**; manual run on a chosen branch: `test:visual:update`, then `test:visual` to prove stability, then commits `web/tests/visual/baselines` to that branch.
- `AGENTS.md`: CI section mentions it.

**Move onto the strata-python library (branch `claude/project-thread-iw7199`)**
Jonathan asked for the shared server code to live in a `strata-python` project (like strata-react) so the template stops duplicating it, and for apps to track its latest. This replaces the template's own copies; behaviour is unchanged except where noted.

- `pyproject.toml`, `uv.lock`: depend on `strata-python` as a git source tracking `main` (the lock pins the commit); pytest options `strata_env_prefix`/`strata_tuning_vars` configure the library's plugin.
- `src/app/oslib.py`, `scripts/check.py`, `tests/utils/http_server.py`, `tests/unit/test_oslib.py`, `tests/unit/test_http_server.py`: **removed**, now `strata_python.oslib`, `strata-check` and the plugin's `http_server` fixture (the library tests them, with real processes and sockets).
- `src/app/settings.py`: declares the two settings with `strata_python.settings.Settings`; same files and `APP_*` variables. Corrections: a bad `data_dir` or blank greeting now raises ValueError from `save` (the API answers 400, as it did for a relative path), `~` in `data_dir` is expanded when saved, and a bad stored or environment value falls back to the default instead of crashing.
- `src/app/server/app.py`, `src/app/cli.py`: health, settings and page routes, `serve`, `doctor` and `set` come from the library; the app keeps its own routes and `hello`/`messages`.
- `tests/conftest.py`: hermetic environment, no-network guard and `http_server` fixture removed (plugin). The `fake_*` fixtures stay as last resorts.
- `scripts/check`, `.github/workflows/unit.yml`: run `strata-check`. `.github/workflows/upgrade-strata-python.yml` **new**: weekly lock upgrade that runs the gate and opens a PR.
- `AGENTS.md`, `README.md`: describe the library, the tracking-main rule and the upgrade workflow.

**Testing policy: real code over mocks (branch `claude/project-thread-iw7199`)**
Asked to steer tests away from mocks towards real HTTP, embedded databases and installed tools, and to make skipping deliberate.

- `AGENTS.md`: **new** Testing policy section (real by default; mocks only for true externals in quick many-case unit tests; install ffmpeg and the like instead of mocking; no silent skips, a skip is a marker with a reason and a switch; machine-heavy tests are marked and run where the machine is).
- `tests/utils/http_server.py`, `tests/unit/test_http_server.py`: **new**. A real loopback HTTP server scripted per test (`http_server` fixture in `tests/conftest.py`); a request no route answers fails the test at teardown.
- `tests/utils/fakes.py`: docstring marks the doubles as a last resort. `tests/README.md`: layout notes point to the policy.
- `pyproject.toml`: ruff `TID` rules selected, `pytest.importorskip` banned with the reason.

**AGENTS.md reorganised as the basis for apps made from the template (branch `claude/project-thread-iw7199`)**
Asked to make the agent instructions suitable as the starting point for future apps, and to point database work at the shared database project.

- `AGENTS.md`: regrouped into rules for every change (run `scripts/check`, changelog and docs in the same commit, comment the why, no secrets or machine-specific details, strict types, tests, report what was run), layout, Python tooling, tests, web, CI and a closing checklist. Says which parts to keep unchanged in a derived app. Content of the earlier bullets is kept.
- `AGENTS.md`: **new** Database section. Apps use [jburnhams/database](https://github.com/jburnhams/database) (one shared database, one schema per app, models and migrations in the app repo, `dbtool check` in CI, never one database per app) and link its adoption guide rather than repeating it.

**Generic deployment notes and a systemd unit example (branch `claude/project-thread-iw7199`)**
A Docker image was dropped from the plan because apps are not deployed that way. These files are deliberately free of machine-specific details.

- `deploy/app.service`: **new**. Example systemd user unit running `uv run --locked --no-dev app serve`.
- `docs/deploying.md`: **new**. Build, install, run, reverse-proxy and how to keep a service file in step with the repo.
- `AGENTS.md`: points to them; the stale `setup_env` mention is gone (corrects the earlier line left behind by the uv change).

**Move the Python side to uv, typed strict, one gate (branch `claude/project-thread-iw7199`)**
Asked for an evaluation of this template against current best practice; the tooling gaps it found are closed here. Behaviour of the app is unchanged.

- `pyproject.toml`: now a real project (`[project]`, hatchling build, `app` console script, `[dependency-groups] dev`), with `--strict-markers --strict-config` for pytest, ruff rules `E,F,I,B,UP,SIM,RUF,C4,PT,S` at line length 120, and pyright strict.
- `uv.lock`, `.python-version`: **new**. Builds are reproducible; CI installs with `uv sync --locked`.
- `requirements.txt`, `requirements-test.txt`, `scripts/setup_env.sh`, `scripts/setup_env.ps1`: **removed**; `uv sync` replaces them. `app` and `app.cmd` stay as thin wrappers over `uv run app`.
- `scripts/check`, `scripts/check.py`: **new**. The one gate (lockfile, ruff lint and format, pyright, ty, unit tests with coverage) for git hooks, agents and CI.
- `src/app/`: fully annotated; `__version__` now reads the package metadata. `oslib.py` relaxes pyright for that one file because its Windows branches use APIs the Linux stubs lack. Formatting is `ruff format` (separate commit, no behaviour change).
- `tests/`: new `test_version.py` and a partial-settings test (coverage is 100% again); a few asserts split for ruff's PT018.
- `.github/workflows/unit.yml`, `integration.yml`: uv with cache; lint, format and types run once on Linux 3.13; weekly `uv audit`. `.github/dependabot.yml`: **new** (uv, npm, actions).
- README, AGENTS.md, test READMEs, docs: commands updated to uv and `scripts/check`.
- Not done yet: Dockerfile and systemd unit, copier conversion, release workflow (next phases).
