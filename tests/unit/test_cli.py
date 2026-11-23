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
    assert "(matching, seed 7)" in first
    assert first.count("\n  * ") == 1
    assert cli.main(["round", "--mode", "matching", "--seed", "7"]) == 0
    assert capsys.readouterr().out == first


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
