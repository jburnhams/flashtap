# Design brief

## 1. Goal

Short, spoken, picture-based rounds, played on a tablet or laptop, with a grown-up choosing what kind. The scope is every school year and every ability, starting with the earliest skills but not limited to them, and progression is by ability, never by age: what a learner is offered next depends on what they have shown they can do, and no age or year group is stored or used to gate content. The longer goal comes from the adaptive learning spec (v0.1, 2026-11-17, written for the early years and widened here): a skill ontology, seeded and validated items, several mechanics, a learner model and a scheduler.

A personal app for private use, in a public repository: nothing in it identifies a person, above all a child (`AGENTS.md`, rule 8). Learner records live only in the deployed database, under a nickname. [implementation-plan.md](implementation-plan.md) maps the way there.

The first rule from that spec, already in force: the server owns the truth (what a round asks and which answer is right), and the browser only draws it and reports taps.

## 2. Architecture

- **Python package (`src/flashtap/`)** on [strata-python](https://github.com/jburnhams/strata-python):
  - `packs/*.toml` and `content/`: the content packs (skills, typed edges with provenance, misconceptions, the phonics sequence, words with their sounds, curriculum goals mapped to skills) and their reader and checker; `flashtap content check` and server start refuse a bad pack ([content.md](content.md)).
  - `lexicon.py`: the words from the `words` pack as the things a round can ask about (an emoji picture, the word, its plural and article, its colour and shape, its first sound from the phonics inventory or none).
  - `mechanics.py`: what a round is, whatever its kind: the eight mechanics in two families (one tap: select one, fill missing, brief exposure, audio respond; an arrangement: give a number, sequence, match pairs, sort), the skills a round gives evidence on and their Q-matrix role (primary, secondary, confound), and `check()`, which refuses a round whose answer is not one and unmistakable.
  - `rounds.py`: the templates, one per kind of round: kind, version, mechanic, skills and the function in `kinds/` that builds its body. A round is a pure function of (kind, version, choices, seed); every round served passes `check()`.
  - `kinds/`: the template bodies (`choose.py`, `place.py`). `distractors.py`: the named generators of wrong options (near number, reversal, confusable grapheme, phonological neighbour), each option naming the one that chose it.
  - `settings.py`: `mode`, `choices`, `tries`, declared with `strata_python.settings` (`~/.flashtap/settings.json`, `FLASHTAP_*` overrides).
  - `learners/`: the learner records on `strata_python.db` (SQLite in tests and with no database configured, the app's schema in the shared Postgres when deployed; migrations in `migrations/`). `models.py`: learners (a random id and a nickname, nothing else), sessions, append-only attempts keyed by the browser's `event_id`, tombstones. `store.py`: writes and reads; the server rebuilds each attempt's round and judges the first answer itself, and a resent event is acknowledged once. `evidence.py`: which attempts count for which skill and why the others do not (first answers only; a wrong answer held back while a confound is unseen; secondary and confound skills credited only for a right answer). `estimators.py`: the rule baseline and BKT behind one interface. `report.py`: the reporting states (unobserved kept apart from every other), the evidence rows and `differences`, which checks a rebuild. Nothing derived is stored: every estimate is computed from the log on read.
  - `server/app.py`: `/api/round`, `/api/modes`, `/api/content`, the learner routes (`/api/learners...`, `/api/attempts...`), plus health, settings and the web app from `strata_python.web`; `landing.html` is a plain stand-in page when the web app is not built.
  - `cli.py`: `doctor`, `round`, `content check|list`, `learners list|rebuild`, `set`, `serve` (`flashtap` console script; `./flashtap` and `flashtap.cmd` wrap it).
- **React frontend (`web/`)** on [strata-react](https://github.com/jburnhams/strata-react):
  - Play (`/`, `?mode=`): the prompt as the page heading (what the round says is spoken on arrival, Say it again), the big picture, then the answer. A one-tap round has tiles: a wrong tap greys that tile and says what it was; the right one is marked and offers Next; a quick look hides its picture after a moment. A placing round has a board: tap a picture, tap its place, then Check, which marks each place right or not yet. With a limit on tries (taps, or checks), running out shows the answer. No score and no streak.
  - Content (`/content`, `?tab=curriculum|phonics`, `?open=<skill>`): the packs for the grown-up: skills by strand with their stage labels and rounds (a row opens to its edges and misconceptions), each curriculum goal mapped or set aside, the phonics sets in order with the words each makes readable.
  - Play also has Who is playing (`?learner=`): with a learner chosen, each round is sent once it ends (or is left half done) with its first answer, tries and outcome; with nobody chosen nothing is sent.
  - Learners (`/learners`): who plays, each a nickname, with rounds recorded and last played; add a learner; Play as a learner.
  - Learner (`/learners/<id>`, `?show=all`, `?open=<skill>`): the finding counts skills by reporting state; each skill row shows BKT's estimate beside the rule baseline's and opens to the rounds behind it (counted or not, and why), where a round can be struck out with Undo; Export downloads everything held; Delete, behind a confirm, removes the learner and every round.
  - Settings (`/settings`, `?tab=appearance`): the server's settings as a form, and the colour scheme.
  - `speech.ts`: the browser's speech synthesis, UK English voice first. `play.ts`: a round's outcome and what to say after a tap or a check, as plain functions.
  - The tap tiles are strata-react's `ChoiceGrid`, the placing board its `PlaceBoard`, and the pictures its `type-picture` step; the screen is Strata components and theme roles only, with no CSS of its own. Faces: Andika (letter shapes children are taught) and Twemoji (the same pictures on every device), both bundled.
  - MSW handlers for every endpoint (`web/src/mocks/`) serve the jsdom tests, Storybook and the visual suite.

## 3. Principles

- Reproducible rounds: the seed is in every round, so a report of "it showed two red ones" can be rebuilt and turned into a test.
- No answer on the tile: a tile carries its word for screen readers only, so Letters and Colours stay listening tasks, not reading tasks.
- No pressure: no points, streaks or timers; mistakes are greyed, never red.
- Hermetic tests, ratcheting coverage floors, strict types: as python-app-template ([AGENTS.md](../AGENTS.md)).
