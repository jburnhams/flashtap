# Design brief

## 1. Goal

Short, spoken, picture-based rounds, played on a tablet or laptop, with a grown-up choosing what kind. The scope is every school year and every ability, starting with the earliest skills but not limited to them, and progression is by ability, never by age: what a learner is offered next depends on what they have shown they can do, and no age or year group is stored or used to gate content. The longer goal comes from the adaptive learning spec (v0.1, 2026-11-17, written for the early years and widened here): a skill ontology, seeded and validated items, several mechanics, a learner model and a scheduler.

A personal app for private use, in a public repository: nothing in it identifies a person, above all a child (`AGENTS.md`, rule 8). Learner records live only in the deployed database, under a nickname. [implementation-plan.md](implementation-plan.md) maps the way there.

The first rule from that spec, already in force: the server owns the truth (what a round asks and which answer is right), and the browser only draws it and reports taps.

## 2. Architecture

- **Python package (`src/flashtap/`)** on [strata-python](https://github.com/jburnhams/strata-python):
  - `lexicon.py`: the things a round can ask about (an emoji picture, the word, its plural and article, its colour and shape, the letter of its first sound or none).
  - `rounds.py`: one generator per kind of round, each a pure function of (mode, choices, seed); `check()` refuses a round with no right answer, two, repeats or too few choices, and every generated round passes through it.
  - `settings.py`: `mode`, `choices`, `tries`, declared with `strata_python.settings` (`~/.flashtap/settings.json`, `FLASHTAP_*` overrides).
  - `server/app.py`: `/api/round`, `/api/modes`, plus health, settings and the web app from `strata_python.web`; `landing.html` is a plain stand-in page when the web app is not built.
  - `cli.py`: `doctor`, `round`, `set`, `serve` (`flashtap` console script; `./flashtap` and `flashtap.cmd` wrap it).
- **React frontend (`web/`)** on [strata-react](https://github.com/jburnhams/strata-react):
  - Play (`/`, `?mode=`): the prompt as the page heading (spoken on arrival, Say it again), the big picture, the tiles. A wrong tap greys that tile and says what it was; the right one is marked and offers Next; with a limit on tries, running out shows the answer. No score and no streak.
  - Settings (`/settings`, `?tab=appearance`): the server's settings as a form, and the colour scheme.
  - `speech.ts`: the browser's speech synthesis, UK English voice first. `play.ts`: a round's outcome and what to say after a tap, as plain functions.
  - Tiles and picture sizes come from `styles/play.css` (Strata's steps are sized for product screens); everything else is Strata components and theme roles. Faces: Andika (letter shapes children are taught) and Twemoji (the same pictures on every device), both bundled.
  - MSW handlers for every endpoint (`web/src/mocks/`) serve the jsdom tests, Storybook and the visual suite.

## 3. Principles

- Reproducible rounds: the seed is in every round, so a report of "it showed two red ones" can be rebuilt and turned into a test.
- No answer on the tile: a tile carries its word for screen readers only, so Letters and Colours stay listening tasks, not reading tasks.
- No pressure: no points, streaks or timers; mistakes are greyed, never red.
- Hermetic tests, ratcheting coverage floors, strict types: as python-app-template ([AGENTS.md](../AGENTS.md)).
