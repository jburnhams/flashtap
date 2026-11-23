"""The HTTP API over a real server on a loopback port (`live_app` from the strata-python plugin)."""

import json
import urllib.request

from strata_python.db.web import database

from flashtap.server.app import create_app


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def test_a_real_server_answers_health_modes_and_rounds(live_app):
    with live_app(create_app()) as base:
        assert _get(f"{base}/api/health")["ok"] is True
        assert len(_get(f"{base}/api/modes")) == 13
        r = _get(f"{base}/api/round?mode=counting&choices=8&seed=99")
        assert len(r["options"]) == 8
        assert _get(f"{base}/api/round?mode=counting&choices=8&seed=99") == r


def test_a_real_server_lists_the_content(live_app):
    with live_app(create_app()) as base:
        s = _get(f"{base}/api/content")
        assert {o["goal"] for o in s["objectives"]} >= {"Number", "Word Reading"}
        assert any(k["modes"] == ["counting"] for k in s["skills"])


def _send(url: str, body: object, method: str = "POST"):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()) if r.status != 204 else None


def test_a_learner_plays_is_exported_and_rebuilt_exactly(live_app, cli_subprocess, tmp_path):
    """The plan's exit criterion end to end: rounds recorded through a real server, the export written to a file, and
    `flashtap learners rebuild` (a real process) reproducing every estimate from the export's events."""
    from flashtap import rounds

    app = create_app()
    with live_app(app) as base:
        fox = _send(f"{base}/api/learners", {"nickname": "Fox"})["id"]
        for seed in range(12):
            mode = rounds.Mode.QUICK_LOOK if seed % 2 else rounds.Mode.COUNTING
            r = _get(f"{base}/api/round?mode={mode}&choices=4&seed={seed}")
            right = seed % 4 != 3
            option = r["answer"] if right else next(o["id"] for o in r["options"] if not o["correct"])
            at = f"2026-11-02T09:{seed:02d}:00Z"
            ack = _send(
                f"{base}/api/attempts",
                {
                    "event_id": f"{seed:032x}", "learner_id": fox, "session_id": "5" * 32, "mode": r["mode"],
                    "version": r["version"], "choices": 4, "seed": r["seed"], "asked": "mixed",
                    "presented_at": at, "answered_at": at, "first_answer": {"option": option},
                    "tries": 1 if right else 2, "outcome": "right",
                },
            )  # fmt: skip
            assert ack["first_correct"] is right
        _send(f"{base}/api/attempts/{3:032x}/strike", {"reason": "a sibling"})
        profile = _get(f"{base}/api/learners/{fox}/profile")
        with urllib.request.urlopen(f"{base}/api/learners/{fox}/export", timeout=10) as r:
            exported = r.read()
    database(app).close()

    states = {s["skill"]: s["state"] for s in profile["skills"]}
    assert states["maths.counting.objects"] != "unobserved"
    assert states["literacy.letters.identify"] == "unobserved"
    saved = tmp_path / "fox.json"
    saved.write_bytes(exported)
    out = cli_subprocess("learners", "rebuild", str(saved))
    assert out.code == 0
    assert "ok: 12 event(s) rebuild the" in out.stdout


def _answer(base: str, fox: str, n: dict, right: bool, at: str) -> None:
    r = n["round"]
    if r["places"]:
        first = {"placement": {k: p["id"] for p in r["places"] for k in p["takes"][: p["holds"]]} if right else {}}
    else:
        first = {"option": r["answer"] if right else next(o["id"] for o in r["options"] if not o["correct"])}
    _send(
        f"{base}/api/attempts",
        {
            "event_id": n["id"][:24] + "a" * 8, "learner_id": fox, "session_id": n["session_id"], "decision_id": n["id"],
            "mode": r["mode"], "version": r["version"], "choices": r["choices"], "seed": r["seed"], "asked": "next",
            "presented_at": at, "answered_at": at, "first_answer": first, "tries": 1 if right else 2, "outcome": "right",
        },
    )  # fmt: skip


def test_the_engine_plans_a_whole_session_that_replays_exactly(live_app, cli_subprocess, tmp_path):
    """The adaptive engine end to end: a session started and played to its end through a real server (rounds answered,
    a break offered and taken up), the decisions replayed by the server, then the export replayed by a real
    `flashtap learners rebuild` process."""
    app = create_app()
    with live_app(app) as base:
        _send(f"{base}/api/settings", {"choices": 3}, method="PUT")
        fox = _send(f"{base}/api/learners", {"nickname": "Fox"})["id"]
        session = _send(f"{base}/api/v1/sessions", {"learner_id": fox})
        actions = []
        for seq in range(40):
            n = _send(f"{base}/api/v1/sessions/{session['id']}/next", {"seq": seq})
            assert _send(f"{base}/api/v1/sessions/{session['id']}/next", {"seq": seq}) == n  # asked again: the same
            actions.append(n["action"])
            if n["action"] == "end":
                break
            if n["action"] == "round":
                assert n["round"]["choices"] == 3
                _answer(base, fox, n, right=seq % 3 != 2, at=f"2026-11-02T09:00:{seq:02d}Z")
        replayed = _send(f"{base}/api/v1/evaluations/replay", {"learner_id": fox})
        with urllib.request.urlopen(f"{base}/api/learners/{fox}/export", timeout=10) as r:
            exported = r.read()
    database(app).close()

    assert actions.count("round") == 20
    assert "break" in actions
    assert actions[-1] == "end"
    assert replayed["decisions"] == len(actions)
    assert (replayed["reproduced"], replayed["differences"]) == (len(actions), [])
    saved = tmp_path / "fox.json"
    saved.write_bytes(exported)
    out = cli_subprocess("learners", "rebuild", str(saved))
    assert out.code == 0
    assert f"ok: {len(actions)} engine decision(s) remade exactly" in out.stdout


def test_engine_simulate_as_a_process_passes_the_exit_criterion(cli_subprocess):
    out = cli_subprocess("engine", "simulate", "--learners", "60", "--sessions", "4")
    assert out.code == 0
    assert out.stdout.strip().endswith("the engine's model beats the rule baseline")
