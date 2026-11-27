"""The application server: `flashtap serve` starts the FastAPI backend and serves the built React app.

    flashtap serve [--host 127.0.0.1] [--port 8361]

API (JSON): GET /api/health; GET and PUT /api/settings {mode?, choices?, tries?} (both from strata_python.web);
GET /api/modes (each kind of round with its mechanic); GET /api/round?mode=&choices=&seed=&version=&level= (each defaults
to the settings; a fresh seed when none is given; a version other than the template's current one is refused with 400;
`level`, a step of difficulty, instead of `choices`, as the engine makes them);
GET /api/rounds?mode=&count=&choices= (count fresh rounds at once, 1 to 20, for a device to keep for when it cannot reach
the server; web/src/reserve.ts); GET /api/content (the content packs as rows: skills, curriculum objectives, phonics sets).
Learner records (src/flashtap/learners/): GET and POST /api/learners {nickname}; PATCH and DELETE /api/learners/{id};
GET /api/learners/{id}/profile (every skill's estimates and state); GET /api/learners/{id}/skills/{skill}/evidence
(the attempts behind it, newest first); GET /api/learners/{id}/export (everything held, as a JSON download);
POST /api/attempts (one round answered; idempotent by event_id); POST /api/attempts/{event_id}/strike {reason};
POST /api/attempts/{event_id}/rating {value} (the three faces: 1, 0 or -1; once per round).
A grown-up's overrides (spec §15): POST /api/v1/learners/{id}/overrides {skill, says, observer, note}; POST
/api/v1/learners/{id}/overrides/{override_id}/withdraw. The profile carries them, and engagement (ratings, picks,
patterns as hypotheses).
The adaptive engine (src/flashtap/engine/): POST /api/v1/sessions {learner_id} (a session it plans, with its settings);
POST /api/v1/sessions/{id}/next {seq} (decision number seq: a round, a break or the end, with rationale codes; asked
again, the same one); POST /api/v1/sessions/{id}/decisions/{seq}/pick {offer} (the learner's pick from a choice of
two, once); POST /api/v1/evaluations/replay {learner_id | simulated} (remake the logged decisions and score
the models' predictions).
The recorded voice (src/flashtap/voice.py): GET /api/v1/voice (each line with a clip, and every phonics sound with its
clip or none); GET /api/v1/voice/clips/{name} (a clip, cached for good: named by its content); PUT
/api/v1/voice/recordings?line=/ʃ/ (a WAV body: a person's recording of a sound, kept over any made one); DELETE
/api/v1/voice/recordings?line=/ʃ/. Talk (src/flashtap/talk.py): GET /api/v1/learners/{id}/talk, what may be said at
each moment around a round, with the learner's nickname filled in.
Background work (src/flashtap/jobs.py, strata_python.tasks.web): GET /api/jobs, /api/jobs/counts, /api/jobs/{id};
POST /api/jobs/{id}/cancel, /api/jobs/{id}/retry. `flashtap serve` queues a talk write and a voice build at every
start; adding or renaming a learner queues one more build.
Every other path serves the web app (`src/flashtap/server/static/index.html` when built with `cd web && npm run build`,
else the plain stand-in `landing.html`), so a reload or a shared link opens that screen: the app routes in the browser."""

import os
import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from strata_python import web
from strata_python.db.web import DbSession, add_database, database
from strata_python.tasks.queue import Queue
from strata_python.tasks.web import add_jobs

from flashtap import __version__, content, jobs, rounds, settings, talk, voice
from flashtap.engine import model, sessions
from flashtap.engine.policy import Config
from flashtap.learners import db as learner_db
from flashtap.learners import store
from flashtap.learners.evidence import Told
from flashtap.learners.report import EvidenceRow, SkillInfo, evidence_rows
from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, SEED_LIMIT, Mechanic, Mode, Round

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
LANDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing.html")
RESERVE_MOST = 20  # rounds a device may ask to keep at once (GET /api/rounds)
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
        level: Annotated[int | None, Query(ge=0)] = None,
    ) -> Round:
        played = mode or settings.mode()
        if level is not None:  # a step of difficulty lays out its own number of choices (rounds.Level)
            if choices is not None:
                raise ValueError("a step of difficulty sets the number of choices: send level or choices, not both")
            r = rounds.at_level(played, level, seed, version)
        else:
            r = rounds.generate(played, choices or settings.choices(), seed, version)
        r.tries = rounds.tries_allowed(settings.tries(), r)
        return r

    @app.get("/api/rounds", response_model=list[Round])
    def get_rounds(  # pyright: ignore[reportUnusedFunction]
        mode: Mode | None = None,
        count: Annotated[int, Query(ge=1, le=RESERVE_MOST)] = 8,
        choices: Annotated[int | None, Query(ge=MIN_CHOICES, le=MAX_CHOICES)] = None,
    ) -> list[Round]:
        # Rounds a device keeps for when it cannot reach the server (web/src/reserve.ts): each made and checked here,
        # fresh seeds, judged here like any other once answered. One request for the lot, so keeping a reserve costs
        # one request every few rounds rather than one per round.
        played = mode or settings.mode()
        n = choices or settings.choices()
        out = [rounds.generate(played, n) for _ in range(count)]
        for r in out:
            r.tries = rounds.tries_allowed(settings.tries(), r)
        return out

    registry = content.load()
    summary = content.summarise(registry, {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})

    @app.get("/api/content", response_model=content.ContentSummary)
    def get_content() -> content.ContentSummary:  # pyright: ignore[reportUnusedFunction]
        return summary  # the packs ship with the app and are read once, so the summary is built once too

    add_database(app, learner_db.PROJECT, default=learner_db.default_url)
    add_learner_routes(
        app, [SkillInfo(id=s.id, title=s.title, domain=s.domain, strand=s.strand) for s in summary.skills]
    )
    add_engine_routes(app, model.graph(registry), {s.id: s.title for s in summary.skills})
    add_voice_routes(app, voice.Store(voice.home()))
    add_jobs(app, lambda: job_queue(app))

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

    # A new nickname is said in the talk lines (flashtap.talk): one more voice build makes its clips before it plays.
    @app.post("/api/learners", response_model=store.LearnerRow, status_code=201)
    def post_learner(body: NicknameIn, s: Db) -> store.LearnerRow:  # pyright: ignore[reportUnusedFunction]
        row = store.add_learner(s, body.nickname)
        jobs.queue_learner_build(job_queue(app))
        return row

    @app.patch("/api/learners/{learner_id}", response_model=store.LearnerRow)
    def patch_learner(learner_id: str, body: NicknameIn, s: Db) -> store.LearnerRow:  # pyright: ignore[reportUnusedFunction]
        row = store.rename_learner(s, learner_id, body.nickname)
        jobs.queue_learner_build(job_queue(app))
        return row

    @app.get("/api/v1/learners/{learner_id}/talk", response_model=talk.TalkOut)
    def get_talk(learner_id: str, s: Db) -> talk.TalkOut:  # pyright: ignore[reportUnusedFunction]
        return talk.pools(talk.Store(voice.home()).read(), store.learner_row(s, learner_id).nickname)

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

    @app.post("/api/attempts/{event_id}/rating", response_model=store.RatingAck)
    def post_rating(event_id: str, body: store.RatingIn, s: Db) -> store.RatingAck:  # pyright: ignore[reportUnusedFunction]
        return store.rate(s, event_id, body)

    known = set(titles)

    @app.post("/api/v1/learners/{learner_id}/overrides", response_model=Told, status_code=201)
    def post_override(learner_id: str, body: store.OverrideIn, s: Db) -> Told:  # pyright: ignore[reportUnusedFunction]
        return store.tell(s, learner_id, body, known)

    @app.post("/api/v1/learners/{learner_id}/overrides/{override_id}/withdraw", status_code=204)
    def post_withdraw(learner_id: str, override_id: str, s: Db) -> Response:  # pyright: ignore[reportUnusedFunction]
        store.withdraw(s, learner_id, override_id)
        return Response(status_code=204)


def add_engine_routes(app: FastAPI, g: model.Graph, titles: dict[str, str]) -> None:
    """The adaptive engine's routes (src/flashtap/engine/; spec §15's /v1 contracts under /api)."""

    @app.post("/api/v1/sessions", response_model=sessions.SessionInfo, status_code=201)
    def post_session(body: sessions.SessionIn, s: Db) -> sessions.SessionInfo:  # pyright: ignore[reportUnusedFunction]
        config = Config(
            choices=settings.choices(),
            tries=settings.tries(),
            max_rounds=settings.session_rounds(),
            max_minutes=settings.session_minutes(),
            break_every=settings.break_every(),
            choice_every=settings.choice_every(),
            rate_every=settings.rate_every(),
        )
        return sessions.start(s, body.learner_id, config)

    @app.post("/api/v1/sessions/{session_id}/next", response_model=sessions.Next)
    def post_next(session_id: str, body: sessions.NextIn, s: Db) -> sessions.Next:  # pyright: ignore[reportUnusedFunction]
        return sessions.next_decision(s, session_id, body.seq, g, titles)

    @app.post("/api/v1/sessions/{session_id}/decisions/{seq}/pick", response_model=sessions.Next)
    def post_pick(session_id: str, seq: int, body: sessions.PickIn, s: Db) -> sessions.Next:  # pyright: ignore[reportUnusedFunction]
        return sessions.pick(s, session_id, seq, body.offer, titles)

    @app.post("/api/v1/evaluations/replay", response_model=sessions.ReplayOut)
    def post_replay(body: sessions.ReplayIn, s: Db) -> sessions.ReplayOut:  # pyright: ignore[reportUnusedFunction]
        return sessions.evaluate(s, body, g)


def add_voice_routes(app: FastAPI, store: voice.Store) -> None:
    """The recorded voice (flashtap.voice): which lines have clips, the clips, and a person's recordings of the sounds."""

    def sound(line: str) -> voice.SoundRow:
        for row in voice.sound_rows(store.read()):
            if row.line == line:
                return row
        raise ValueError(f"{line!r} is not a sound of the phonics inventory: only sounds are recorded here")

    @app.get("/api/v1/voice", response_model=voice.VoiceOut)
    def get_voice() -> voice.VoiceOut:  # pyright: ignore[reportUnusedFunction]
        return voice.voice_out(store)

    @app.get("/api/v1/voice/clips/{name}", response_class=FileResponse)
    def get_clip(name: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        path = store.path_of(name)
        if path is None or not path.is_file():
            raise HTTPException(404, f"no clip {name}")
        # named by the hash of its bytes, so a clip never changes under its name: the browser keeps it
        return FileResponse(
            path, media_type="audio/wav", headers={"Cache-Control": "public, max-age=31536000, immutable"}
        )

    @app.put("/api/v1/voice/recordings", response_model=voice.SoundRow)
    async def put_recording(line: str, request: Request) -> voice.SoundRow:  # pyright: ignore[reportUnusedFunction]
        sound(line)
        wav = await request.body()
        if len(wav) > voice.MAX_RECORDING_BYTES:
            raise ValueError(f"a recording is at most {voice.MAX_RECORDING_S:g} seconds")
        store.put(line, wav, source="recorded", voice="recording")  # read_wav refuses what is not a short PCM WAV
        return sound(line)

    @app.delete("/api/v1/voice/recordings", status_code=204)
    def delete_recording(line: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        c = store.clip(sound(line).line)
        if c is None or c.source != "recorded":
            raise HTTPException(404, f"no recording of {line}")
        store.remove(line)
        return Response(status_code=204)


def job_queue(app: FastAPI) -> Queue:
    """The app's job queue, on its database, made on first use (the routes' first request, or `run_jobs` at start)."""
    q: Queue | None = getattr(app.state, "jobs", None)
    if q is None:
        q = app.state.jobs = jobs.queue(database(app).engine())
    return q


def run_jobs(app: FastAPI, *, isolate: bool = True) -> FastAPI:
    """Run the background work while `app` serves: at start-up, queue a voice build and start the worker (which opens
    the database, so a served app always has one); at shutdown, stop it. Only `main` (`flashtap serve`) asks for it,
    so an app made in a test or by `openapi` starts no worker and asks strata-models for nothing."""
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(a: Any) -> AsyncGenerator[Any]:
        async with inner(a) as state:
            worker = jobs.start(job_queue(app), isolate=isolate)
            try:
                yield state
            finally:
                worker.stop()

    app.router.lifespan_context = lifespan
    return app


def main(argv: Sequence[str] | None = None) -> None:
    web.serve(run_jobs(create_app()), argv, default_port=PORT, banner=f"settings: {settings.SETTINGS.path()}")
