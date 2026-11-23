"""The application server: `flashtap serve` starts the FastAPI backend and serves the built React app.

    flashtap serve [--host 127.0.0.1] [--port 8361]

API (JSON): GET /api/health; GET and PUT /api/settings {mode?, choices?, tries?} (both from strata_python.web);
GET /api/modes; GET /api/round?mode=&choices=&seed= (each defaults to the settings; a fresh seed when none is given);
GET /api/content (the content packs as rows: skills, curriculum objectives, phonics sets).
Every other path serves the web app (`src/flashtap/server/static/index.html` when built with `cd web && npm run build`,
else the plain stand-in `landing.html`), so a reload or a shared link opens that screen: the app routes in the browser."""

import os
from collections.abc import Sequence
from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel
from strata_python import web

from flashtap import __version__, content, rounds, settings
from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, SEED_LIMIT, Mode, Round

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
LANDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing.html")
PORT = 8361  # python-app-template's 8360 plus one, so both can run on one machine


class ModeInfo(BaseModel):
    mode: Mode
    name: str
    description: str


def create_app() -> FastAPI:
    # health, settings and (last) the web app's page routes come from the shared library; the routes between are this app's own
    app = web.base_app("flashtap", __version__, settings.SETTINGS, commit=web.source_commit(__file__))
    web.add_error_handlers(app)  # ValueError -> 400 with its sentence, as ErrorBody

    @app.get("/api/modes", response_model=list[ModeInfo])
    def get_modes() -> list[ModeInfo]:  # pyright: ignore[reportUnusedFunction]
        return [ModeInfo(mode=m, name=n, description=d) for m, (n, d) in rounds.MODE_NAMES.items()]

    @app.get("/api/round", response_model=Round)
    def get_round(  # pyright: ignore[reportUnusedFunction]
        mode: Mode | None = None,
        choices: Annotated[int | None, Query(ge=MIN_CHOICES, le=MAX_CHOICES)] = None,
        seed: Annotated[int | None, Query(ge=0, lt=SEED_LIMIT)] = None,
    ) -> Round:
        r = rounds.generate(mode or settings.mode(), choices or settings.choices(), seed)
        r.tries = rounds.tries_allowed(settings.tries(), len(r.options))
        return r

    summary = content.summarise(content.load(), {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})

    @app.get("/api/content", response_model=content.ContentSummary)
    def get_content() -> content.ContentSummary:  # pyright: ignore[reportUnusedFunction]
        return summary  # the packs ship with the app and are read once, so the summary is built once too

    web.add_web(app, STATIC, LANDING)
    return app


def main(argv: Sequence[str] | None = None) -> None:
    web.serve(create_app(), argv, default_port=PORT, banner=f"settings: {settings.SETTINGS.path()}")
