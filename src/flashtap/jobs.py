"""Work the server does on its own, on strata-python's job queue (`strata_python.tasks.queue`; 0.14.0).

One kind today, **voice build**: make every line Flashtap says that has no clip yet, or whose clip came from another
speak model or other settings (`voice.build`, what `flashtap voice build` runs). The owner asked for it to happen by
itself: new rounds bring new sentences (the first steps did), and a deploy restarts the server, so `start` queues one
build each time the server starts. `dedupe` keeps it to one at a time however often the server restarts, and the
`voice` resource keeps two builds from writing the clip store at once.

A build that leaves lines unmade (strata-models is away, or busy with something larger) raises `RetryLater`, so the
queue runs it again after `RETRY_S`, up to its retries (`RETRIES`); each run makes only what is still missing. A
line that fails every time ends the job as failed, its sentence in `error` (`GET /api/jobs`), and the next start tries
again. Consonant sounds are never made, only listed: a person records them on the Sounds screen.

The queue's table is in the learner records' schema (`learners.models.JOBS`); the worker runs in the server process
(`server/app.py` `run_jobs`), each job in a process of its own at idle priority, so play never waits on it.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.engine import Engine
from strata_python.tasks.progress import report_progress
from strata_python.tasks.queue import Job, Queue, Worker
from strata_python.tasks.retry import RetryLater

from flashtap import voice
from flashtap.learners.models import JOBS

VOICE_BUILD = "voice_build"
RETRY_S = 15 * 60.0  # strata-models restarts, or finishes a long batch, in minutes; no need to ask every few seconds
RETRIES = 8  # about two hours of trying, then the next start


def voice_build(job: Job) -> dict[str, Any]:
    """Make the clips that are missing or stale; the counts, and the sounds left to record, as the job's result.
    Options: `limit`, the first that many lines only (as `flashtap voice build --limit`), for a quick build."""
    wanted = voice.lines()
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
    return {"made": len(r.made), "kept": len(r.kept), "to_record": r.to_record}


HANDLERS: dict[str, Callable[[Job], Any]] = {VOICE_BUILD: voice_build}


def queue(engine: Engine) -> Queue:
    return Queue(engine, JOBS, retries=RETRIES)


def start(q: Queue, *, isolate: bool = True) -> Worker:
    """Queue the start-up build (or find the one already queued) and start a worker for every kind here."""
    q.enqueue(VOICE_BUILD, dedupe=True, resources=["voice"])
    return Worker(q, HANDLERS, isolate=isolate, lower_priority=True).start()
