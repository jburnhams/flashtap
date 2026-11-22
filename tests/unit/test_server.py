import pytest
from fastapi.testclient import TestClient

from flashtap.server import app as server_app
from flashtap.server.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_landing_page_and_built_static_index(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATIC", str(tmp_path / "no_static"))
    c = TestClient(create_app())
    assert "Flashtap" in c.get("/").text
    assert c.get("/api/health").json()["ok"] is True

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<h1>built react app</h1>", encoding="utf8")
    (static / "assets" / "main.js").write_text("console.log(1)", encoding="utf8")
    monkeypatch.setattr(server_app, "STATIC", str(static))
    c2 = TestClient(create_app())
    assert c2.get("/").text == '<base href="./"><h1>built react app</h1>'
    assert c2.get("/settings/x").text == '<base href="../"><h1>built react app</h1>'
    assert "console.log(1)" in c2.get("/assets/main.js").text
    assert c2.get("/api/nope").status_code == 404


def test_modes_lists_every_mode(client):
    modes = client.get("/api/modes").json()
    assert [m["mode"] for m in modes] == ["matching", "colours", "shapes", "letters", "counting", "mixed"]
    assert modes[0]["name"] == "Matching"


def test_round_takes_its_defaults_from_the_settings(client):
    assert client.put("/api/settings", json={"mode": "shapes", "choices": "6", "tries": "2"}).status_code == 200
    r = client.get("/api/round").json()
    assert r["mode"] == "shapes"
    assert len(r["options"]) == 6
    assert r["tries"] == 2
    assert client.get("/api/round", params={"seed": r["seed"]}).json() == r


def test_round_query_overrides_and_no_limit_on_tries(client):
    r = client.get("/api/round", params={"mode": "letters", "choices": 3, "seed": 11}).json()
    assert r["mode"] == "letters"
    assert len(r["options"]) == 3
    assert r["tries"] is None
    assert sum(o["correct"] for o in r["options"]) == 1


@pytest.mark.parametrize("params", [{"choices": 9}, {"choices": 1}, {"mode": "spelling"}, {"seed": -1}])
def test_bad_round_queries_are_refused(client, params):
    assert client.get("/api/round", params=params).status_code == 422


def test_settings_refuse_a_bad_value(client):
    assert client.put("/api/settings", json={"choices": "12"}).status_code == 400
    assert client.get("/api/settings").json() == {"mode": "mixed", "choices": "4", "tries": "0"}
