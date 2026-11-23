# Changelog

Newest first, grouped by day. One entry per change, in the same commit or PR as the change.

## 2026-11-23

**Flashtap 0.4.0: the mechanics, seven new kinds of round (branch `claude/project-thread-3qzxl1`)**
The owner asked for the next PR of the plan (PR 3, the mechanics): templates that declare their Q-matrix roles, the eight mechanics and named distractor generators, with every round rebuilt from (template, version, seed) and 1,000 seeds per template checked for an ambiguous key.

- `src/flashtap/mechanics.py`: **new**. `Mode` (now 12 kinds plus Mixed), `Mechanic` (8, in two families), `QRole` and `SkillRole`, `Option` (gains `distractor`), `Piece`, `Place` (`takes`, `holds`), `Round` (gains `version`, `choices`, `mechanic`, `skills`, `say`, `exposure_ms`, `pieces`, `places`, `done_feedback`), `check` for both families, `arranged_right`.
- `src/flashtap/distractors.py`: **new**. Near numbers, reversals (6 and 9, 12 and 21), confusable letters (b d p q, m w, n u), phonological neighbours (one feature apart, from a draft feature table), and `fill`.
- `src/flashtap/kinds/`: **new**. `choose.py` (the five original kinds, now with named distractors, Letters preferring look-alike and near-sound words; Missing number, Quick look, Listen) and `place.py` (Give a number, Order, Capitals, Sort by sound).
- `src/flashtap/rounds.py`: now the template table (kind, version, mechanic, name, description, skills with roles, body), `generate(mode, choices, seed, version)` and `tries_allowed(tries, round)` (checks, on a placing round). **Correction**: a Mixed round's reported kind and seed did not rebuild it (the kind was drawn from the round's own generator first); Mixed now picks the kind and then the round's own seed.
- `src/flashtap/lexicon.py`: `letters` (the one-letter GPCs) and `sound_words`.
- `src/flashtap/server/app.py`: `GET /api/round` takes `version` (another version: 400 with the reason); `GET /api/modes` gives each kind's mechanic. `landing.html`: plays one-tap rounds, hides a quick look's picture after `exposure_ms` (Codex review), and says a placing round needs the web app.
- `src/flashtap/cli.py`: `round --version`; the text output names the version, mechanic, what is said, each wrong option's generator, and where pieces go.
- `tests/unit/test_rounds.py` (rewritten: 1,000 seeds of every template, per-kind rules, `check` refusals for both families), `test_distractors.py` (**new**), `test_cli.py`, `test_server.py`, `tests/integration/test_server_api.py`.
- `web/package.json`, `web/package-lock.json`: strata-react ^1.3.0, for `PlaceBoard` (strata-react PR #285); a checked place's mark is in its name ("first, right"), so `PlayScreen.test.tsx` asks for it there.
- `web/src/screens/PlayScreen.tsx`: a round is answered by `ChoiceGrid` or, for the four placing mechanics, by `PlaceBoard` and a Check button (each place marked Right or Not yet until its contents change; running out of checks shows the arrangement). A quick look hides its picture after `exposure_ms`, keeping its room; the spoken text is the round's `say`.
- `web/src/play.ts`: `placeRight`, `arrangedRight`, `solution`, `placeOutcome`, `placeFeedback` (giving a number says how many were given). `web/src/api.ts`: the new kinds and round fields.
- `web/src/mocks/fixtures.ts`, `handlers.ts`: a round per new kind (from `flashtap round --json`), modes with mechanics, `quickLookGoes` and `quickLookStays`.
- `web/tests/unit/logic.test.ts`, `web/tests/integration/PlayScreen.test.tsx`: the arrangement logic and each new kind on the screen; web coverage stays 100%.
- `web/stories/play.stories.tsx`, `web/strata-visual.config.ts`, `web/tests/visual/baselines/`: **new** shots for the seven new kinds, a checked Order and Give a number (24 baselines); the 78 others are unchanged.
- `pyproject.toml`, `uv.lock`: version 0.4.0.
- `docs/implementation-plan.md`, `docs/progress.md`, `docs/overview.md`, `README.md`, `AGENTS.md`, `tests/unit/README.md`, `web/tests/README.md`, `web/stories/introduction.mdx`: the mechanics, templates and the new kinds.

**Flashtap 0.3.0: content packs, the P0 ontology seed, with an adult Content screen (branch `claude/project-thread-ghe3ix`)**
The owner asked for the next PR of the plan: content packs for the earliest skills (numbers to 10, early phonics) in a structure that grows through every school year, by ability and never by age. YAML became TOML (standard library, no new dependency).

- `src/flashtap/content/`: **new**. `model.py` (pydantic models for sources, domains, strands, parameter dimensions, skills with typed edges carrying confidence and source, misconceptions, phonics sequences, words, curricula and objectives; unknown keys refused), `registry.py` (reads `packs/*.toml`, one id space, edges turned to one direction, GPC resolution and decodability, `check` for dangling references, duplicate ids, `prerequisite_strong` and `part_of` cycles, parameter ranges, word spellings, unmapped objectives; `load()` refuses bad packs at start), `summary.py` (the rows `GET /api/content` returns).
- `src/flashtap/packs/`: **new**, all `status = "draft"`. `core.toml` (sources, domains, dimensions), `maths-number.toml` (22 skills: verbal count, counting, cardinality, subitising, numerals, comparison, part-whole, patterns, 2D shapes; 5 misconceptions), `literacy-early.toml` (19 skills, 4 misconceptions), `language.toml` (3 skills), `phonics-letters-and-sounds.toml` (Phases 2 and 3, 51 GPCs in IPA), `words.toml` (71 words with pictures and sounds), `curriculum-uk-eyfs.toml` (the 15 maths and literacy Early Learning Goal statements, 12 mapped, 3 out of scope with reasons).
- `src/flashtap/lexicon.py`: words now come from `words.toml`; `initial` is replaced by `onset`, the first GPC from the phonics inventory. Matching, Counting and Letters gain the new picture words of their categories.
- Review fixes (Codex on PR #40): `lexicon.words()` reads the packs on first use, not at import, so `flashtap content check` still starts and names the problems when a packaged pack is broken; an empty range (`number_range = []`) is reported instead of raising `IndexError`; `content.load(folder)` takes the folder, so its test reads real files instead of replacing `build`.
- `src/flashtap/rounds.py`: `MODE_SKILLS`, the skills each kind of round practises; `MAX_CHOICES` comment corrected.
- `src/flashtap/cli.py`: `flashtap content check [--packs DIR]` and `flashtap content list [--json]`.
- `src/flashtap/server/app.py`: `GET /api/content`.
- `web/src/screens/ContentScreen.tsx`: **new** Content screen (`/content`): drafts or coverage as the finding, a `MetricStrip`, tabs for Skills (a `DataTable` whose rows open to their edges and misconceptions, open rows and sort in the URL), Curriculum and Phonics. `Layout.tsx`: Content in the menu. `routes.tsx`, `api.ts` (types, path, key): the screen and its endpoint.
- `web/src/mocks/content.ts`: **new** fixture cut down from `flashtap content list --json`; `handlers.ts`: the endpoint plus loading, error, empty and all-reviewed states.
- `web/stories/content.stories.tsx`: **new**, every state. `web/strata-visual.config.ts`: Content route shots. `web/stories/introduction.mdx`: the screen.
- `web/tests/visual/baselines/`: Content shots are new; every other screen's shots change because the menu has a third entry.
- `tests/unit/test_content.py`: **new**. `tests/unit/test_cli.py`, `test_server.py`, `tests/integration/test_cli_end_to_end.py`, `test_server_api.py`, `web/tests/integration/ContentScreen.test.tsx` (**new**): the commands, the endpoint and the screen.
- `pyproject.toml`, `uv.lock`: version 0.3.0; Python coverage floor 95 to 98 (the suite is at 99).
- `docs/content.md`: **new**, the pack format, its rules and what is left to review. `docs/implementation-plan.md`, `docs/progress.md`, `docs/overview.md`, `README.md`, `AGENTS.md`, `tests/unit/README.md`, `web/tests/README.md`: describe the packs, the command, the endpoint and the screen.

**Play screen on strata-react's `ChoiceGrid` (branch `claude/project-thread-fmqqff`)**
The tap tiles were the one part of the Play screen drawn in Flashtap's own CSS until strata-react had a component for them; strata-react 1.1.5 ships `ChoiceGrid` (strata-react PR #281), so the stand-in goes.

- `web/package.json`, `web/package-lock.json`: strata-react ^1.1.5.
- `web/src/screens/PlayScreen.tsx`: the tiles are a `ChoiceGrid` (React Aria grid: arrow keys move across and down, Enter answers; closed tiles cannot be pressed again) and the skeleton a `ChoiceGridSkeleton`; the big picture uses `type-picture`. The answer key and the spoken feedback stay here. The tap handler's own "already tapped or finished" guard is gone, as `ChoiceGrid` no longer delivers those taps.
- `web/src/styles/theme.css`: `--type-picture-size` raised (3rem to 5rem): strata-react's default drew a 35px emoji in a 138px phone tile.
- `web/src/styles/play.css`: **removed**; `web/src/styles/app.css` no longer imports it.
- `web/tests/integration/PlayScreen.test.tsx`: tiles are found as rows of the "Choices" grid, named by their picture and then their mark ("duck, not this one").
- `web/tests/visual/baselines/`: Play and Counting shots rewritten (the tiles' border, gap and mark now come from `ChoiceGrid`).
- `docs/overview.md`, `docs/implementation-plan.md`, `web/stories/introduction.mdx`: no longer mention `play.css`.

**Scope and privacy: every school year, progression by ability, nothing identifying (branch `claude/project-thread-fmqqff`)**
The owner answered the plan's open questions: Flashtap is a personal app for private use in a public repository, so it must hold nothing identifying, above all about children; and it covers every school year and ability, starting with the youngest but not limited to them, progressing by ability rather than age.

- `AGENTS.md`: **new** rule 8, nothing that identifies a person (no names, ages, birth dates, year groups, schools, places, photos, voices or learner data anywhere in the repository; invented learners in tests; the learner model stores no age). "What this is" no longer says early years.
- `tests/unit/test_privacy.py`: **new**. Scans the repository's text files for an age, a birth date or a birthday; it caught `play.css` calling the player "a three-year-old".
- `docs/implementation-plan.md`: decisions recorded with their answers; a Scope paragraph (curriculum stages are labels on skills, never gates; placement by probes; no age stored); PR 2's schema covers every year, PR 4's learner holds only a nickname, PR 5 places by evidence.
- `README.md`, `docs/overview.md`, `pyproject.toml`, `src/flashtap/__init__.py`, `web/stories/introduction.mdx`: describe Flashtap by ability, not by age, and say the repository is public.
- `web/src/speech.ts`, `web/src/styles/play.css`, `web/src/styles/theme.css`, `web/src/styles/theme.generated.css` (header comment only): comments no longer assume a young child.
- `tests/unit/README.md`: ledger row for the privacy test.
- `CHANGELOG.md`, `docs/implementation-plan.md`: the owner is no longer named (Codex review on PR #39); `AGENTS.md` rule 8 says people are never named, `LICENSE`'s copyright line excepted.

## 2026-11-22

**Flashtap 0.2.0: a Python web app on strata-python and strata-react (branch `claude/project-thread-fmqqff`)**
The owner asked to change Flashtap from a React/TypeScript npm library into a Python web app on strata-python and strata-react, then to plan growing it toward his early-years adaptive learning spec. This is PR 1 of that plan (`docs/implementation-plan.md`): the same five kinds of round, now owned by the server, with the old generators' bugs fixed. The entries below this one are python-app-template's history, which Flashtap was built from.

- `src/`, `tests/`, `docs/` (demo site), `package.json`, `package-lock.json`, `tsconfig*.json`, `vite.config.ts`, `vitest*.config.ts`, `playwright.config.ts`, `.github/workflows/{browser-tests,deploy-docs,integration-tests,node.js,npm-publish,release}.yml`: **removed** (the npm library and its CI).
- python-app-template's files copied in, with `src/app` renamed `src/flashtap`, `app`/`app.cmd` renamed `flashtap`/`flashtap.cmd`, port 8361, and the sample greetings, log and status page removed (`greet.py`, `system.py`, their screens, stories and tests). `upgrade-strata-python.yml` removed: strata-python now comes from PyPI (`strata-python>=0.2,<0.3`).
- `pyproject.toml`, `uv.lock`: package `flashtap` 0.2.0, MIT, `hypothesis` for property tests, `FLASHTAP_*` environment.
- `src/flashtap/lexicon.py`: **new**. Every word with its plural and article written down ("sheep", "an elephant", "some grapes") and its first sound for Letters (chicken and cheese left out: "What starts with C?" must not mix two sounds); aeroplane in UK English.
- `src/flashtap/rounds.py`: **new**. Seeded rounds (same mode, choices and seed give the same round) checked for exactly one right answer, no repeats and enough choices. Corrections to the old generators: Colours offered two red shapes for "Which one is red?", Counting looped forever above ten choices, tiles printed their own names (Letters and Colours became reading tasks), and plurals and articles were built by string templates.
- `src/flashtap/settings.py`, `src/flashtap/server/app.py`, `src/flashtap/server/landing.html`, `src/flashtap/cli.py`: **new**. Settings mode, choices (2 to 8) and tries (0 for no limit); `GET /api/modes`, `GET /api/round`; `flashtap round`.
- `web/src/`: **new** Play screen (prompt said aloud, en-GB voice first; a wrong tap greys the tile and says what it was; the right tap or running out of tries shows the answer and Next; no score) and Settings screen; `api.ts`, `play.ts`, `speech.ts`, mocks, routes. `styles/play.css` is the tile layout's stand-in until strata-react has a tap-tile component. Fonts Andika and Twemoji (COLR; Noto's SVG emoji font renders blank in Chromium); palette regenerated from blackboard green and pencil yellow.
- `web/tests/`, `web/stories/`, `web/strata-visual.config.ts`: tests and stories for both screens; coverage floors 100. 52 visual baselines, written here in Chromium 157 because the pinned 158 could not be downloaded and the *Update visual baselines* workflow cannot be dispatched until it is on `main`; strata-react's suite matches CI's 158 within its tolerance on this Chromium for most shots. If CI's run differs, rewrite them with that workflow after merge.
- Review fixes on PR #36: `src/flashtap/cli.py` prints rounds as UTF-8 (Windows' cp1252 console could not print an emoji, failing `python -m flashtap round` there); `SettingsScreen.tsx` reads the list of kinds of round through its own `DataView` (it fell back silently on an error); `PlayScreen.tsx` drops every cached round on Next, the one on screen too, so changing the kind and back asks for a new round rather than replaying the first; `mocks/handlers.ts` counts round requests and gains `modesError`, `modesFew`; tests for each.
- `tests/`: unit and integration suites for the above; `fail_under` 95.
- `README.md`, `AGENTS.md`, `NOTICE`, `docs/{overview,implementation-plan,progress,deploying}.md`, `deploy/flashtap.service`, `tests/**/README.md`, `web/tests/README.md`, `docs/prompts/`: describe Flashtap. `AGENTS.md`: what Strata lacks is now added to strata-react rather than raised as an issue (the owner, 2026-11-22).

## 2026-11-09

**Regenerate visual baselines on the CI runner (branch `claude/project-thread-iw7199`)**
The owner wants every dependency kept current, including Dependabot's playwright and lucide-react bumps. Those change the Chromium or the icons behind every screenshot, and a laptop cannot reproduce the CI Chromium, so the baselines are now written by a manual workflow.

- `.github/workflows/update-visual-baselines.yml`: **new**; manual run on a chosen branch: `test:visual:update`, then `test:visual` to prove stability, then commits `web/tests/visual/baselines` to that branch.
- `AGENTS.md`: CI section mentions it.

**Move onto the strata-python library (branch `claude/project-thread-iw7199`)**
The owner asked for the shared server code to live in a `strata-python` project (like strata-react) so the template stops duplicating it, and for apps to track its latest. This replaces the template's own copies; behaviour is unchanged except where noted.

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
