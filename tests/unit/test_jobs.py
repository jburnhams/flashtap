"""Background work (flashtap.jobs) on a real SQLite queue, with strata-models' speak call answered by the plugin's
`fake_models` stand-in (the true external edge): a build makes what is missing, keeps what is there, runs again later
when lines are left unmade or it was stopped, and the served app queues one and stops it with the server.
tests/integration/test_jobs.py runs the same through a served app."""

import time
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from strata_python.db.web import database
from strata_python.testing import sine_wav

from flashtap import jobs, voice
from flashtap.server.app import create_app, job_queue, run_jobs


def until(done: Callable[[], bool], seconds: float = 120.0) -> None:
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


def test_a_short_build_makes_its_lines_and_a_second_finds_nothing_to_make(fake_models, tmp_path):
    speaker(fake_models, tmp_path)
    app = create_app()
    q = job_queue(app)
    q.enqueue(jobs.VOICE_BUILD, {"limit": 3})
    done = q.step(jobs.HANDLERS)
    assert done is not None
    finished = q.get(done.id)
    assert finished is not None
    assert finished.state == "done"
    assert finished.result == {"made": 3, "kept": 0, "to_record": []}
    q.enqueue(jobs.VOICE_BUILD, {"limit": 3})
    again = q.step(jobs.HANDLERS)
    assert again is not None
    kept = q.get(again.id)
    assert kept is not None
    assert kept.result == {"made": 0, "kept": 3, "to_record": []}
    assert len(fake_models.jobs) == 3
    database(app).close()


def test_a_build_with_lines_left_unmade_runs_again_later(fake_models, tmp_path):
    speaker(fake_models, tmp_path)
    fake_models.fail("CUDA out of memory", role="speak")
    app = create_app()
    q = job_queue(app)
    first = q.enqueue(jobs.VOICE_BUILD, {"limit": 2})
    ran = q.step(jobs.HANDLERS)
    assert ran is not None
    later = q.get(first)
    assert later is not None
    assert later.state == "queued"  # to run again, not failed
    assert later.run_after is not None
    assert later.run_after - time.time() > jobs.RETRY_S - 60
    assert later.error is not None
    assert "1 of 2 lines" in later.error
    assert "CUDA out of memory" in later.error
    database(app).close()


def test_a_build_asked_to_stop_leaves_the_rest_and_runs_again_at_once(fake_models, tmp_path):
    speaker(fake_models, tmp_path)
    app = create_app()
    q = job_queue(app)
    jid = q.enqueue(jobs.VOICE_BUILD, {"limit": 4})
    job = q.claim(list(jobs.HANDLERS))
    assert job is not None
    assert job.id == jid
    job.stop_event.set()  # as the worker does when the server shuts down
    q.run(job, jobs.voice_build)
    after = q.get(jid)
    assert after is not None
    assert after.state == "queued"
    assert after.error is not None
    assert "stopped with 4 of 4 lines still to do" in after.error
    assert fake_models.jobs == []  # stopped between clips: none was asked for
    database(app).close()


def test_the_served_app_queues_a_build_at_start_and_stops_its_worker_with_the_server(fake_models, tmp_path):
    speaker(fake_models, tmp_path)
    voice.lines()  # swept once per process (about a minute cold), so the worker starts on the lines at once
    app = run_jobs(create_app(), isolate=False)
    with TestClient(app) as client:
        until(lambda: len(fake_models.jobs) >= 2)
        (task,) = client.get("/api/jobs").json()["items"]
        assert (task["kind"], task["state"]) == (jobs.VOICE_BUILD, "running")
        assert client.get("/api/jobs/counts").json()["running"] == 1
    (job,) = job_queue(app).page().items
    assert job.state == "queued"  # stopped with the server: the rest next start
    database(app).close()
