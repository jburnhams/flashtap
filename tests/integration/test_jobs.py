"""Background work end to end (flashtap.jobs): a served app queues a voice build when it starts, its worker makes clips
through the strata-models stand-in over real HTTP, and stopping the server leaves the rest queued for the next start.
The job's rules are tests/unit/test_jobs.py."""

import time
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from strata_python.db.web import database
from strata_python.testing import sine_wav

from flashtap import jobs, voice
from flashtap.server.app import create_app, job_queue, run_jobs


# The build's first clip waits for `voice.lines()`, a sweep of every template over thousands of seeds: about 50 s on
# Linux and about 120 s on a Windows runner, where 120 s here failed at 0.22.0 (3,732 lines, 3,634 before). The wait
# is for the sweep, not for the job, so it is generous.
def until(done: Callable[[], bool], seconds: float = 300.0) -> None:
    end = time.monotonic() + seconds
    while not done():
        assert time.monotonic() < end, "the job did not finish in time"
        time.sleep(0.2)


def speaker(fake_models, tmp_path: Path) -> None:
    def speak(params: dict[str, object]) -> dict[str, object]:
        path = tmp_path / f"tts-{len(fake_models.jobs)}.wav"
        path.write_bytes(sine_wav(0.2, rate=24000))
        return {"path": str(path), "voice": params["voice"], "duration_s": 0.2}

    fake_models.results["speak"] = speak
    fake_models.models["speak"] = "kokoro-v1"


def test_serving_starts_a_voice_build_by_itself_and_stopping_leaves_the_rest_for_next_time(fake_models, tmp_path):
    speaker(fake_models, tmp_path)
    app = run_jobs(create_app(), isolate=False)  # threads here, so the stand-in's URL needs no handing on
    with TestClient(app) as client:
        until(lambda: sum(j["role"] == "speak" for j in fake_models.jobs) >= 3)  # making clips, a line at a time
        items = {t["kind"]: t for t in client.get("/api/jobs").json()["items"]}
        assert items[jobs.VOICE_BUILD]["state"] == "running"
        assert jobs.TALK_WRITE in items  # the talk is written at each start too (the stand-in has no write role)
    have = voice.Store(voice.home()).read().clips
    assert have  # what was made before the stop is kept
    q = job_queue(app)
    job = next(j for j in q.page().items if j.kind == jobs.VOICE_BUILD)
    after = q.get(job.id)
    assert after is not None
    assert after.state == "queued"  # the rest is still to do: queued again, not done and not failed
    assert after.error is not None
    assert "stopped with" in after.error
    # The next start finds it queued (dedupe) rather than adding a second build
    assert jobs.queue(database(app).engine()).enqueue(jobs.VOICE_BUILD, dedupe=True, resources=["voice"]) == job.id
    database(app).close()
