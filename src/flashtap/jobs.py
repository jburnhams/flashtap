"""Work the server does on its own, on strata-python's job queue (`strata_python.tasks.queue`; 0.14.0).

Two kinds. **Talk write** (0.17.0): fill the pools of varied lines around a round (`talk.write`, the write role of
strata-models), then queue a voice build so they are said in the recorded voice. **Voice build**: make every line
Flashtap says that has no clip yet, or whose clip came from another speak model or other settings (`voice.build`,
what `flashtap voice build` runs), with the talk lines filled in for every learner's nickname (`voice.wanted`). The owner asked for it to happen by
itself: new rounds bring new sentences (the first steps did), and a deploy restarts the server, so `start` queues one
build each time the server starts. `dedupe` keeps it to one at a time however often the server restarts, and the
`voice` resource keeps two builds from writing the clip store at once.

A build that leaves lines unmade (strata-models is away, or busy with something larger) raises `RetryLater`, so the
queue runs it again after `RETRY_S`, up to its retries (`RETRIES`); each run makes only what is still missing. A
line that fails every time ends the job as failed, its sentence in `error` (`GET /api/jobs`), and the next start tries
again. Every phonics sound is made too (strata-models' `sound`); a recording made on the Sounds screen is kept over it.
A learner added or renamed queues one more build (`learner_build`), so their name is said before they first play.

The queue's table is in the learner records' schema (`learners.models.JOBS`); the worker runs in the server process
(`server/app.py` `run_jobs`), each job in a process of its own at idle priority, so play never waits on it.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.engine import Engine
from strata_python.tasks.progress import report_progress
from strata_python.tasks.queue import Job, Queue, Worker
from strata_python.tasks.retry import RetryLater

from flashtap import talk, voice
from flashtap.learners import db as learner_db
from flashtap.learners import store
from flashtap.learners.models import JOBS

VOICE_BUILD = "voice_build"
TALK_WRITE = "talk_write"
RETRY_S = 15 * 60.0  # strata-models restarts, or finishes a long batch, in minutes; no need to ask every few seconds
RETRIES = 8  # about two hours of trying, then the next start


def voice_build(job: Job) -> dict[str, Any]:
    """Make the clips that are missing or stale; the counts, and the sounds left to record, as the job's result.
    Options: `limit`, the first that many lines only (as `flashtap voice build --limit`), for a quick build."""
    wanted = voice.wanted(nicknames()) if job.options.get("talk", True) else voice.lines()
    limit = job.options.get("limit")
    if isinstance(limit, int) and limit > 0:
        wanted = wanted[:limit]
    done = 0

    def said(line: str) -> None:
        nonlocal done
        done += 1
        report_progress(done, len(wanted), line)

    r = voice.build(voice.Store(voice.home()), wanted, now=voice.speak_settings(), say=said, stop=lambda: job.stopping)
    if r.left:  # stopped between clips (the server shutting down): the rest next time, which may be at once
        raise RetryLater(f"stopped with {len(r.left)} of {len(wanted)} lines still to do", after_s=0)
    if r.failed:
        line, why = next(iter(r.failed.items()))
        raise RetryLater(f"{len(r.failed)} of {len(wanted)} lines not made yet; {line}: {why}", after_s=RETRY_S)
    return {"made": len(r.made), "kept": len(r.kept)}


def nicknames() -> list[str]:
    """Every learner's nickname, from the learner records (the job runs in a process of its own, so it opens them)."""
    from sqlalchemy.orm import Session

    with Session(learner_db.open_engine()) as s:
        return [x.nickname for x in store.list_learners(s)]


def talk_write(job: Job) -> dict[str, Any]:
    """Fill the talk pools (`talk.write`), then queue a voice build for what was written. Moments the write role did
    not answer are tried again later; what was written is voiced at once either way."""
    keys = list(talk.moments())
    done = 0

    def said(line: str) -> None:
        nonlocal done
        done += 1
        report_progress(done, len(keys), line)

    w = talk.write(talk.Store(voice.home()), keys, say=said, stop=lambda: job.stopping)
    if any(w.added.values()):
        queue_learner_build(queue(learner_db.open_engine()))  # the job runs in a process of its own: its own engine
    if w.left:
        raise RetryLater(f"stopped with {len(w.left)} of {len(keys)} moments still to write", after_s=0)
    if w.failed:
        key, why = next(iter(w.failed.items()))
        raise RetryLater(f"{len(w.failed)} of {len(keys)} moments not written yet; {key}: {why}", after_s=RETRY_S)
    if w.short:  # the model answered, but too few lines passed the checks: ask again, up to the queue's retries
        raise RetryLater(f"{len(w.short)} of {len(keys)} moments not full yet; {w.short[0]}", after_s=RETRY_S)
    return {"added": sum(w.added.values()), "full": len(w.full), "refused": sum(map(len, w.refused.values()))}


HANDLERS: dict[str, Callable[[Job], Any]] = {VOICE_BUILD: voice_build, TALK_WRITE: talk_write}


def queue(engine: Engine) -> Queue:
    return Queue(engine, JOBS, retries=RETRIES)


def start(q: Queue, *, isolate: bool = True) -> Worker:
    """Queue the start-up talk and build (or find the ones already queued) and start a worker for every kind here."""
    q.enqueue(TALK_WRITE, dedupe=True, resources=["talk"])
    q.enqueue(VOICE_BUILD, dedupe=True, resources=["voice"])
    return Worker(q, HANDLERS, isolate=isolate, lower_priority=True).start()


def queue_learner_build(q: Queue) -> None:
    """One more voice build after any running now (a learner added, or new talk written): its own dedupe key, so it
    waits behind a build already running, which read the nicknames when it started, instead of being folded into it."""
    q.enqueue(VOICE_BUILD, {"after": "learners"}, dedupe=True, resources=["voice"])
