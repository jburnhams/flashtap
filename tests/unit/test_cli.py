import importlib
import json
from pathlib import Path

from strata_python.db.web import database
from strata_python.testing import assert_openapi_current

from flashtap import cli
from flashtap.server.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_doctor_success_and_missing_module(capsys, monkeypatch):
    assert cli.main(["doctor"]) == 0
    assert "fastapi" in capsys.readouterr().out

    real_import = importlib.import_module

    def fake_import(name, *a):
        if name == "uvicorn":
            raise ImportError("no uvicorn")
        return real_import(name, *a)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    assert cli.main(["doctor"]) == 1


def test_round_prints_the_same_round_for_a_seed(capsys):
    assert cli.main(["round", "--mode", "matching", "--seed", "7"]) == 0
    first = capsys.readouterr().out
    assert "(matching v1, select_one, seed 7)" in first
    assert "(same_category)" in first
    assert first.count("\n  * ") == 1
    assert cli.main(["round", "--mode", "matching", "--seed", "7"]) == 0
    assert capsys.readouterr().out == first


def test_round_prints_what_is_said_and_where_pieces_go(capsys):
    assert cli.main(["round", "--mode", "listen", "--seed", "2"]) == 0
    assert "  said: " in capsys.readouterr().out
    assert cli.main(["round", "--mode", "give", "--seed", "2", "--version", "1"]) == 0
    out = capsys.readouterr().out
    assert "  pieces: " in out
    assert "🧺: " in out
    assert " of " in out
    assert cli.main(["round", "--mode", "order", "--seed", "2"]) == 0
    assert "first: " in capsys.readouterr().out


def test_round_json_follows_the_settings(capsys):
    assert cli.main(["set", "mode", "counting"]) == 0
    assert cli.main(["set", "choices", "5"]) == 0
    capsys.readouterr()
    assert cli.main(["round", "--json", "--seed", "3"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["mode"] == "counting"
    assert len(r["options"]) == 5


def test_serve_starts_the_server_on_the_default_port(monkeypatch):
    from flashtap.server import app as server_app

    called = []
    monkeypatch.setattr(server_app, "main", lambda argv: called.append(argv))
    assert cli.main(["serve"]) == 0
    assert called == [["--host", "127.0.0.1", "--port", "8361"]]


def test_content_check_passes_on_the_shipped_packs(capsys):
    assert cli.main(["content", "check"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("ok: 8 packs, ")
    assert "15 objectives (12 mapped, 3 out of scope)" in out


def test_content_check_names_each_problem(tmp_path, capsys):
    (tmp_path / "bad.toml").write_text(
        'pack = "bad"\nversion = 1\ntitle = "Bad"\nstatus = "draft"\n'
        '[[skills]]\nid = "x.a"\ntitle = "A"\nstrand = "x.nowhere"\n',
        encoding="utf-8",
    )
    assert cli.main(["content", "check", "--packs", str(tmp_path)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "x.a: strand 'x.nowhere' does not exist",
        "1 problem(s) in 1 pack(s)",
    ]


def test_content_list_prints_skills_by_strand(capsys):
    assert cli.main(["content", "list"]) == 0
    out = capsys.readouterr().out
    assert "Mathematics / Counting objects\n" in out
    assert "  maths.counting.objects  Count a set of things  (eyfs, played in counting, played in which_group)\n" in out
    assert "  maths.counting.one_to_one  Touch or tag each thing once  (played in give, played in number_card)\n" in out
    assert "  maths.verbal_count.decades  Count across a decade  (eyfs)\n" in out  # no kind of round plays it yet


def test_content_list_json_is_the_api_shape(capsys):
    assert cli.main(["content", "list", "--json"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert set(s) == {"packs", "skills", "objectives", "phonics"}
    assert len(s["objectives"]) == 15


def test_learners_list_and_rebuild(capsys, tmp_path):
    from fastapi.testclient import TestClient

    from flashtap.server.app import create_app

    assert cli.main(["learners", "list"]) == 0
    assert "no learners yet" in capsys.readouterr().out
    app = create_app()
    c = TestClient(app)
    fox = c.post("/api/learners", json={"nickname": "Fox"}).json()["id"]
    assert cli.main(["learners", "list"]) == 0
    assert f"{fox}  Fox  0 round(s), last played never" in capsys.readouterr().out

    export = c.get(f"/api/learners/{fox}/export").json()
    saved = tmp_path / "fox.json"
    saved.write_text(json.dumps(export), encoding="utf-8")
    assert cli.main(["learners", "rebuild", str(saved)]) == 0
    assert "ok: 0 event(s) rebuild the" in capsys.readouterr().out
    assert cli.main(["learners", "rebuild", str(saved), "--current-packs"]) == 0
    capsys.readouterr()

    export["skills"][0]["state"] = "retained"
    saved.write_text(json.dumps(export), encoding="utf-8")
    assert cli.main(["learners", "rebuild", str(saved)]) == 1
    out = capsys.readouterr().out
    assert "state was 'retained', rebuilt 'unobserved'" in out
    assert "1 difference(s) rebuilding 0 event(s)" in out
    database(app).close()


def test_engine_simulate_prints_the_scores_and_exits_1_when_the_rule_wins(capsys):
    from flashtap.engine import simulate

    r = simulate.report(8, 2, 3)
    assert cli.main(["engine", "simulate", "--learners", "8", "--sessions", "2", "--seed", "3"]) == (
        0 if r.beats_rule else 1
    )
    assert capsys.readouterr().out.splitlines() == list(simulate.describe(r))
    cli.main(["engine", "simulate", "--learners", "8", "--sessions", "2", "--seed", "3", "--json"])
    assert simulate.SimReport.model_validate_json(capsys.readouterr().out) == r


def test_rebuild_remakes_the_engine_decisions_in_an_export(capsys, tmp_path):
    from fastapi.testclient import TestClient

    from flashtap.server.app import create_app

    app = create_app()
    c = TestClient(app)
    fox = c.post("/api/learners", json={"nickname": "Fox"}).json()["id"]
    sid = c.post("/api/v1/sessions", json={"learner_id": fox}).json()["id"]
    for seq in range(3):
        c.post(f"/api/v1/sessions/{sid}/next", json={"seq": seq})
    export = c.get(f"/api/learners/{fox}/export").json()
    saved = tmp_path / "fox.json"
    saved.write_text(json.dumps(export), encoding="utf-8")
    assert cli.main(["learners", "rebuild", str(saved)]) == 0
    assert "ok: 3 engine decision(s) remade exactly" in capsys.readouterr().out
    export["decisions"][1]["seed"] = 1
    saved.write_text(json.dumps(export), encoding="utf-8")
    assert cli.main(["learners", "rebuild", str(saved)]) == 1
    out = capsys.readouterr().out
    assert f"decision 1 of session {sid}: seed was 1, remade" in out
    assert "1 difference(s) rebuilding 0 event(s) and 3 decision(s)" in out
    database(app).close()


def test_openapi_writes_the_schema_and_the_committed_file_is_current(capsys, tmp_path):
    # web/openapi.json is what the web app's types are generated from (web CI checks that step with --check), so a
    # change to a response model that is not written back fails here, naming the command that fixes it.
    assert_openapi_current(create_app, ROOT / "web" / "openapi.json")
    out = tmp_path / "openapi.json"
    assert cli.main(["openapi", "-o", str(out)]) == 0
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert schema["paths"]["/api/round"]["get"]["responses"]["200"]
    # A round always carries every field, so the generated type has no optional ones to check for.
    assert "options" in schema["components"]["schemas"]["Round"]["required"]
    # The kind of round is a setting with fixed values, so the schema (and the web type) names them.
    assert "mixed" in schema["components"]["schemas"]["FlashtapSettings"]["properties"]["mode"]["enum"]
    assert cli.main(["openapi", "-o", str(out), "--check"]) == 0


def test_voice_lines_status_and_a_build_with_no_service(capsys, monkeypatch):
    """The recorded voice from the CLI with nothing made yet. With no strata-models to reach, `build` names each line
    it could not make and fails; tests/integration runs it against the service's stand-in."""
    from strata_python.testing import sine_wav

    from flashtap import voice

    voice.Store(voice.home()).put("/ʃ/", sine_wav(0.5, rate=24000), source="recorded", voice="recording")
    assert cli.main(["voice", "lines"]) == 0
    out = capsys.readouterr().out
    assert "recorded   /ʃ/" in out
    assert "missing    Listen." in out
    assert cli.main(["voice", "lines", "--missing"]) == 0
    assert "/ʃ/" not in capsys.readouterr().out
    assert cli.main(["voice", "status"]) == 0
    out = capsys.readouterr().out
    assert "sounds:    1 of 45 have a clip" in out
    assert "/m/" in out.split("not made yet")[1]
    assert "/ʃ/" not in out.split("not made yet")[1].split("\n")[0]
    assert "recorded on the Sounds screen: /ʃ/" in out
    assert "voices: recording" in out

    monkeypatch.setenv("STRATA_MODELS_URL", "http://127.0.0.1:9")  # the discard port: nothing answers
    assert cli.main(["voice", "build", "--only", "sentences", "--limit", "1"]) == 1
    assert "FAILED 0:" in capsys.readouterr().out
    assert cli.main(["voice", "build", "--only", "sounds", "--limit", "1"]) == 1  # /s/: made too, so it fails here
    assert "made 0, kept 0, failed 1" in capsys.readouterr().out


def test_talk_write_list_and_strike(capsys, monkeypatch):
    """The talk from the CLI: with no strata-models to reach, `write` names each moment it could not write and fails;
    `list` shows the fixed and written lines, `strike` takes one out for good. tests/unit/test_jobs.py writes through
    the service's stand-in."""
    from flashtap import talk, voice

    store = talk.Store(voice.home())
    store.edit(lambda b: b.lines.update({"right": [talk.Written(text="Lovely, {name}!", made="2026-11-27")]}))
    assert cli.main(["talk", "list", "right", "retry"]) == 0
    out = capsys.readouterr().out
    assert "right  (fixed: Yes!)\n  Lovely, {name}!" in out
    assert "retry  (fixed: Try again.)" in out
    assert "intro.counting" not in out
    assert cli.main(["talk", "strike", "Lovely, {name}!"]) == 0
    assert "struck from 1 moments" in capsys.readouterr().out
    assert cli.main(["talk", "strike", "Not one."]) == 0
    assert "not a written line" in capsys.readouterr().out
    assert store.read().lines["right"] == []

    monkeypatch.setenv("STRATA_MODELS_URL", "http://127.0.0.1:9")  # the discard port: nothing answers
    assert cli.main(["talk", "write", "right"]) == 1
    assert "FAILED right:" in capsys.readouterr().out
