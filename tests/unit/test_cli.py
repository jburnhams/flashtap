import importlib
import json

from flashtap import cli


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
    assert out.startswith("ok: 7 packs, ")
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
    assert "  maths.counting.objects  Count a set of things  (eyfs, played in counting)\n" in out
    assert "  maths.counting.one_to_one  Touch or tag each thing once  (played in give)\n" in out
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
    app.state.learner_engine.dispose()
