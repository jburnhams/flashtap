# Flashtap

Learning games for every school year and ability, starting with the earliest skills: a spoken question, a big picture, and two to eight tiles to tap, exactly one of them right. Progression follows what a learner can show they can do, never their age. A personal app for private use; the repository is public, so it holds no detail that identifies anyone (see `AGENTS.md`, rule 8). A Python web app (FastAPI + CLI on [strata-python](https://github.com/jburnhams/strata-python)) with a React frontend on [strata-react](https://github.com/jburnhams/strata-react), shaped like [python-app-template](https://github.com/jburnhams/python-app-template).

Twelve kinds of round today, over eight ways of answering: tap one picture (Matching, Colours, Shapes, Letters, Counting), fill the missing number (Missing number), say how many after a quick look (Quick look), hear a word and tap its first letter (Listen), and four answered by moving pictures with two taps: Give a number, Order, Capitals (match pairs) and Sort by sound; plus Mixed. The server builds every round from a template, a version and a seed and checks that its answer is one and unmistakable before sending, so a round can be rebuilt exactly; each wrong option names the generator that chose it (a near number, a reversed 6 or 9, a look-alike letter, a sound one feature away). What it can teach is described in content packs (TOML in `src/flashtap/packs/`: skills with typed, sourced prerequisite edges, a phonics sequence in IPA, words with their sounds, and the EYFS Early Learning Goals mapped onto skills), shown on the Content screen; see [docs/content.md](docs/content.md). A grown-up can add learners (a nickname, nothing else) and choose who is playing; each round they answer is recorded, judged by the server from the rebuilt round, and the Learner screen shows every skill's estimates (Bayesian knowledge tracing beside a simple recent-answers rule), a reporting state (not seen yet, introduced, emerging, independent, generalised, retained) and the rounds behind each one, with export and delete. Or the grown-up picks "Chosen for them" and the adaptive engine chooses each round: it places a new learner with a few probes through the skill graph (from their answers, never an age), practises what is ready, brings back what may be fading, follows a miss with a round that leaves part of it out, offers a break after a run of misses or every ten rounds and ends the session at twenty rounds or fifteen minutes, saying why each time; every decision is logged with what else it weighed and replays exactly. Where this is going, towards an adaptive learning engine with a skill ontology, a learner model and a scheduler, is in [docs/implementation-plan.md](docs/implementation-plan.md).

Until 0.1.9 Flashtap was an npm React component library; 0.2.0 replaces it with this app (see [CHANGELOG.md](CHANGELOG.md)).

## Quick start

```bash
uv sync                                   # creates .venv from uv.lock (install uv: https://docs.astral.sh/uv/)
cd web && npm ci && npm run build && cd ..   # builds the web app into src/flashtap/server/static/ (Node 26, .nvmrc)
uv run flashtap serve                     # http://127.0.0.1:8361/
uv run flashtap round --mode counting     # one round in the terminal; --seed N gives the same round again
uv run flashtap content check            # the content packs: no dangling edges, no prerequisite cycles, every goal mapped or set aside
uv run flashtap learners list             # the learners; `learners rebuild export.json` checks an export's estimates and engine decisions against its events
uv run flashtap engine simulate           # simulated learners: each model's held-out log loss, and skills learnt under the engine vs at random
uv run flashtap set choices 6             # settings: mode, choices (2-8), tries (0 = no limit)
uv run flashtap doctor                    # check the environment
```

Without the web build, `flashtap serve` answers with a plain stand-in page that still plays rounds. For hot-reload frontend work, run `uv run flashtap serve` in one terminal and `cd web && npm run dev` in another (Vite proxies `/api` to port 8361).

## API

| Endpoint | What it does |
| --- | --- |
| `GET /api/round?mode=&choices=&seed=&version=` | One checked round; each parameter defaults to the settings, and a fresh seed is picked (and returned) when none is sent; a template version other than the current one is refused (400) |
| `GET /api/modes` | The kinds of round, with a name, a sentence and the mechanic each |
| `GET /api/content` | The content packs as rows: skills (with stage labels, rounds and edges), curriculum goals, phonics sets |
| `GET`, `POST /api/learners`; `PATCH`, `DELETE /api/learners/{id}` | List and add learners (`{nickname}`), rename, delete with everything recorded |
| `GET /api/learners/{id}/profile` | Every skill's estimates (`bkt@1`, `rule@1`), reporting state, counts and last seen |
| `GET /api/learners/{id}/skills/{skill}/evidence` | The rounds that touched a skill, newest first: the first answer, whether it counted and why not |
| `GET /api/learners/{id}/export` | Everything held about a learner, as a JSON download |
| `POST /api/attempts` | One round answered (`event_id`, the round's kind, version, choices and seed, the first answer, tries, outcome, and the engine's `decision_id` when it chose the round); idempotent by `event_id` |
| `POST /api/attempts/{event_id}/strike` | Strike a round out of every estimate (`{reason}`); the round stays in the log |
| `POST /api/v1/sessions` | Start a session the adaptive engine plans (`{learner_id}`), with a snapshot of its settings |
| `POST /api/v1/sessions/{id}/next` | Decision number `seq` (`{seq}`): a round, an offered break or the end, with rationale codes, the reason in words and every candidate weighed; asked again, the same decision |
| `POST /api/v1/evaluations/replay` | Remake a learner's logged decisions and score each model's predictions (`{learner_id}`), or run a simulation (`{simulated: {learners, sessions, seed}}`) |
| `GET`, `PUT /api/settings` | `mode`, `choices`, `tries` (from strata-python) |
| `GET /api/health` | `ok`, `version`, `commit` |
| `GET /api/docs` | The OpenAPI page |

## Documentation

| Document | What it is |
| --- | --- |
| [docs/overview.md](docs/overview.md) | The design brief: goals, architecture, layout |
| [docs/implementation-plan.md](docs/implementation-plan.md) | The plan from here to an adaptive learning engine (from the adaptive learning spec), PR by PR |
| [docs/content.md](docs/content.md) | Content packs: what they hold, how to write one, what the check refuses |
| [docs/progress.md](docs/progress.md) | The log of what was tried, measured and decided |
| [docs/deploying.md](docs/deploying.md) | Running it as a service |
| [AGENTS.md](AGENTS.md) | Repository conventions and commands (for people and coding agents) |

## Tests

```bash
scripts/check                                   # the gate (strata-check): lockfile, ruff, pyright strict, ty, unit tests + coverage
uv run pytest tests/integration                 # the CLI and HTTP API end-to-end
cd web && npm run typecheck && npm run test:coverage:gate   # web unit + jsdom tests against coverage-floor.json
uv run flashtap openapi && cd web && npm run api-types    # after a response model changes: the schema, then the web app's types from it
cd web && npm run storybook                     # every screen in every server state, on :6006
cd web && npm run test:visual                   # screenshots of the stories and routes, light and dark, against tests/visual/baselines/
```

Visual baselines must come from the Chromium of the pinned Playwright (`web/package.json`); write them on the CI runner with the "Update visual baselines" workflow. See [tests/README.md](tests/README.md) and [web/tests/README.md](web/tests/README.md).

## Licences

MIT ([LICENSE](LICENSE)). The pictures are [Twemoji](https://github.com/jdecked/twemoji) (graphics CC-BY 4.0) through `twemoji-colr-font` (OFL-1.1), and the face is [Andika](https://software.sil.org/andika/) (OFL-1.1); see [NOTICE](NOTICE).
