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
    assert [m["mode"] for m in modes] == [
        "matching", "colours", "shapes", "letters", "counting",
        "missing", "quick_look", "listen", "give", "order", "capitals", "sort_sounds", "mixed",
    ]  # fmt: skip
    assert modes[0] == {
        "mode": "matching",
        "name": "Matching",
        "description": modes[0]["description"],
        "mechanic": "select_one",
    }
    assert modes[-1]["mechanic"] is None


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


@pytest.mark.parametrize("params", [{"choices": 9}, {"choices": 1}, {"mode": "spelling"}, {"seed": -1}, {"version": 0}])
def test_bad_round_queries_are_refused(client, params):
    assert client.get("/api/round", params=params).status_code == 422


def test_a_place_round_and_a_template_version_no_longer_kept(client):
    r = client.get("/api/round", params={"mode": "give", "seed": 5, "version": 1}).json()
    assert r["mechanic"] == "give_n"
    assert r["options"] == []
    assert r["places"][0]["word"] == "the basket"
    bad = client.get("/api/round", params={"mode": "give", "seed": 5, "version": 2})
    assert bad.status_code == 400
    assert "version 2 is not kept" in bad.json()["detail"]


def test_settings_refuse_a_bad_value(client):
    assert client.put("/api/settings", json={"choices": "12"}).status_code == 400
    assert client.get("/api/settings").json() == {"mode": "mixed", "choices": "4", "tries": "0"}


def test_content_lists_skills_objectives_and_phonics(client):
    s = client.get("/api/content").json()
    skills = {k["id"]: k for k in s["skills"]}
    assert skills["literacy.gpc.initial_letter"]["modes"] == ["letters"]
    assert skills["maths.subitising.perceptual"]["stages"] == ["eyfs"]
    assert sum(1 for o in s["objectives"] if o["out_of_scope"]) == 3
    assert s["phonics"][0]["sets"][0]["gpcs"][1] == {"grapheme": "a", "phoneme": "æ", "example": "ant"}
