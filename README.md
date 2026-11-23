# Flashtap

Early years learning games for children of about three to seven: a spoken question, a big picture, and two to eight tiles to tap, exactly one of them right. A Python web app (FastAPI + CLI on [strata-python](https://github.com/jburnhams/strata-python)) with a React frontend on [strata-react](https://github.com/jburnhams/strata-react), shaped like [python-app-template](https://github.com/jburnhams/python-app-template).

Five kinds of round today: Matching, Colours, Shapes, Letters and Counting, plus Mixed. The server builds every round from a seed and checks it before sending (one right answer, no repeats), so a round can be rebuilt exactly. Where this is going, towards an adaptive learning engine with a skill ontology, a learner model and a scheduler, is in [docs/implementation-plan.md](docs/implementation-plan.md).

Until 0.1.9 Flashtap was an npm React component library; 0.2.0 replaces it with this app (see [CHANGELOG.md](CHANGELOG.md)).

## Quick start

```bash
uv sync                                   # creates .venv from uv.lock (install uv: https://docs.astral.sh/uv/)
cd web && npm ci && npm run build && cd ..   # builds the web app into src/flashtap/server/static/ (Node 26, .nvmrc)
uv run flashtap serve                     # http://127.0.0.1:8361/
uv run flashtap round --mode counting     # one round in the terminal; --seed N gives the same round again
uv run flashtap set choices 6             # settings: mode, choices (2-8), tries (0 = no limit)
uv run flashtap doctor                    # check the environment
```

Without the web build, `flashtap serve` answers with a plain stand-in page that still plays rounds. For hot-reload frontend work, run `uv run flashtap serve` in one terminal and `cd web && npm run dev` in another (Vite proxies `/api` to port 8361).

## API

| Endpoint | What it does |
| --- | --- |
| `GET /api/round?mode=&choices=&seed=` | One checked round; each parameter defaults to the settings, and a fresh seed is picked (and returned) when none is sent |
| `GET /api/modes` | The kinds of round, with a name and a sentence each |
| `GET`, `PUT /api/settings` | `mode`, `choices`, `tries` (from strata-python) |
| `GET /api/health` | `ok`, `version`, `commit` |
| `GET /api/docs` | The OpenAPI page |

## Documentation

| Document | What it is |
| --- | --- |
| [docs/overview.md](docs/overview.md) | The design brief: goals, architecture, layout |
| [docs/implementation-plan.md](docs/implementation-plan.md) | The plan from here to the early years adaptive learning spec, PR by PR |
| [docs/progress.md](docs/progress.md) | The log of what was tried, measured and decided |
| [docs/deploying.md](docs/deploying.md) | Running it as a service |
| [AGENTS.md](AGENTS.md) | Repository conventions and commands (for people and coding agents) |

## Tests

```bash
scripts/check                                   # the gate (strata-check): lockfile, ruff, pyright strict, ty, unit tests + coverage
uv run pytest tests/integration                 # the CLI and HTTP API end-to-end
cd web && npm run typecheck && npm run test:coverage:gate   # web unit + jsdom tests against coverage-floor.json
cd web && npm run storybook                     # every screen in every server state, on :6006
cd web && npm run test:visual                   # screenshots of the stories and routes, light and dark, against tests/visual/baselines/
```

Visual baselines must come from the Chromium of the pinned Playwright (`web/package.json`); write them on the CI runner with the "Update visual baselines" workflow. See [tests/README.md](tests/README.md) and [web/tests/README.md](web/tests/README.md).

## Licences

MIT ([LICENSE](LICENSE)). The pictures are [Twemoji](https://github.com/jdecked/twemoji) (graphics CC-BY 4.0) through `twemoji-colr-font` (OFL-1.1), and the face is [Andika](https://software.sil.org/andika/) (OFL-1.1); see [NOTICE](NOTICE).
