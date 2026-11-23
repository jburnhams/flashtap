"""The application server: `flashtap serve` starts the FastAPI backend and serves the built React app.

    flashtap serve [--host 127.0.0.1] [--port 8361]

API (JSON): GET /api/health; GET and PUT /api/settings {mode?, choices?, tries?} (both from strata_python.web);
GET /api/modes (each kind of round with its mechanic); GET /api/round?mode=&choices=&seed=&version= (each defaults to the
settings; a fresh seed when none is given; a version other than the template's current one is refused with 400);
GET /api/content (the content packs as rows: skills, curriculum objectives, phonics sets).
Learner records (src/flashtap/learners/): GET and POST /api/learners {nickname}; PATCH and DELETE /api/learners/{id};
GET /api/learners/{id}/profile (every skill's estimates and state); GET /api/learners/{id}/skills/{skill}/evidence
(the attempts behind it, newest first); GET /api/learners/{id}/export (everything held, as a JSON download);
POST /api/attempts (one round answered; idempotent by event_id); POST /api/attempts/{event_id}/strike {reason}.
Every other path serves the web app (`src/flashtap/server/static/index.html` when built with `cd web && npm run build`,
else the plain stand-in `landing.html`), so a reload or a shared link opens that screen: the app routes in the browser."""

import os
import re
from collections.abc import Sequence
from typing import Annotated

from fastapi import FastAPI, Query, Response
from pydantic import BaseModel
from strata_python import web
from strata_python.db.web import DbSession, add_database

from flashtap import __version__, content, rounds, settings
from flashtap.learners import db as learner_db
from flashtap.learners import store
from flashtap.learners.report import EvidenceRow, SkillInfo, evidence_rows
from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, SEED_LIMIT, Mechanic, Mode, Round

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
LANDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing.html")
PORT = 8361  # python-app-template's 8360 plus one, so both can run on one machine


class ModeInfo(BaseModel):
    mode: Mode
    name: str
    description: str
    mechanic: Mechanic | None  # None for Mixed, which plays every kind


class NicknameIn(BaseModel):
    nickname: str


class StrikeIn(BaseModel):
    reason: str = ""


def create_app() -> FastAPI:
    # health, settings and (last) the web app's page routes come from the shared library; the routes between are this app's own
    app = web.base_app("flashtap", __version__, settings.SETTINGS, commit=web.source_commit(__file__))
    web.add_error_handlers(app)  # ValueError -> 400 with its sentence, as ErrorBody

    @app.get("/api/modes", response_model=list[ModeInfo])
    def get_modes() -> list[ModeInfo]:  # pyright: ignore[reportUnusedFunction]
        return [
            ModeInfo(mode=m, name=n, description=d, mechanic=t.mechanic if (t := rounds.TEMPLATES.get(m)) else None)
            for m, (n, d) in rounds.MODE_NAMES.items()
        ]

    @app.get("/api/round", response_model=Round)
    def get_round(  # pyright: ignore[reportUnusedFunction]
        mode: Mode | None = None,
        choices: Annotated[int | None, Query(ge=MIN_CHOICES, le=MAX_CHOICES)] = None,
        seed: Annotated[int | None, Query(ge=0, lt=SEED_LIMIT)] = None,
        version: Annotated[int | None, Query(ge=1)] = None,
    ) -> Round:
        r = rounds.generate(mode or settings.mode(), choices or settings.choices(), seed, version)
        r.tries = rounds.tries_allowed(settings.tries(), r)
        return r

    summary = content.summarise(content.load(), {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})

    @app.get("/api/content", response_model=content.ContentSummary)
    def get_content() -> content.ContentSummary:  # pyright: ignore[reportUnusedFunction]
        return summary  # the packs ship with the app and are read once, so the summary is built once too

    add_database(app, learner_db.PROJECT, default=learner_db.default_url)
    add_learner_routes(
        app, [SkillInfo(id=s.id, title=s.title, domain=s.domain, strand=s.strand) for s in summary.skills]
    )

    web.add_web(app, STATIC, LANDING)
    return app


# The learner records: opened (and migrated) on the first request that needs them, once per app, so serving rounds
# never waits on the database and a server nobody records on never creates one (strata_python.db.web).
Db = DbSession


def add_learner_routes(app: FastAPI, skills: list[SkillInfo]) -> None:
    """The learner records' routes (src/flashtap/learners/)."""
    titles = {s.id: s.title for s in skills}

    @app.get("/api/learners", response_model=list[store.LearnerRow])
    def get_learners(s: Db) -> list[store.LearnerRow]:  # pyright: ignore[reportUnusedFunction]
        return store.list_learners(s)

    @app.post("/api/learners", response_model=store.LearnerRow, status_code=201)
    def post_learner(body: NicknameIn, s: Db) -> store.LearnerRow:  # pyright: ignore[reportUnusedFunction]
        return store.add_learner(s, body.nickname)

    @app.patch("/api/learners/{learner_id}", response_model=store.LearnerRow)
    def patch_learner(learner_id: str, body: NicknameIn, s: Db) -> store.LearnerRow:  # pyright: ignore[reportUnusedFunction]
        return store.rename_learner(s, learner_id, body.nickname)

    @app.delete("/api/learners/{learner_id}", status_code=204)
    def delete_learner(learner_id: str, s: Db) -> Response:  # pyright: ignore[reportUnusedFunction]
        store.delete_learner(s, learner_id)
        return Response(status_code=204)

    @app.get("/api/learners/{learner_id}/profile", response_model=store.Profile)
    def get_profile(learner_id: str, s: Db) -> store.Profile:  # pyright: ignore[reportUnusedFunction]
        return store.profile(s, learner_id, skills)

    @app.get("/api/learners/{learner_id}/skills/{skill}/evidence", response_model=list[EvidenceRow])
    def get_evidence(learner_id: str, skill: str, s: Db) -> list[EvidenceRow]:  # pyright: ignore[reportUnusedFunction]
        store.get_learner(s, learner_id)
        return evidence_rows(store.events(s, learner_id), skill, titles)

    @app.get("/api/learners/{learner_id}/export", response_model=store.Export)
    def get_export(learner_id: str, s: Db, response: Response) -> store.Export:  # pyright: ignore[reportUnusedFunction]
        out = store.export(s, learner_id, skills)
        name = re.sub(r"[^A-Za-z0-9]+", "-", out.learner.nickname).strip("-").lower() or "learner"
        response.headers["Content-Disposition"] = f'attachment; filename="flashtap-{name}.json"'
        return out

    @app.post("/api/attempts", response_model=store.Ack)
    def post_attempt(body: store.AttemptIn, s: Db) -> store.Ack:  # pyright: ignore[reportUnusedFunction]
        return store.record(s, body)

    @app.post("/api/attempts/{event_id}/strike", status_code=204)
    def post_strike(event_id: str, body: StrikeIn, s: Db) -> Response:  # pyright: ignore[reportUnusedFunction]
        store.strike(s, event_id, body.reason)
        return Response(status_code=204)


def main(argv: Sequence[str] | None = None) -> None:
    web.serve(create_app(), argv, default_port=PORT, banner=f"settings: {settings.SETTINGS.path()}")
