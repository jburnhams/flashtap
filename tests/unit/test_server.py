import pytest
from fastapi.testclient import TestClient
from strata_python.db.web import database

from flashtap.server import app as server_app
from flashtap.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    yield TestClient(app)
    database(app).close()  # the learner database, if a learner route opened it


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
    assert client.get("/api/settings").json() == {
        "mode": "mixed",
        "choices": 4,
        "tries": 0,
    }  # numbers: Settings(numbers=True)


def test_content_lists_skills_objectives_and_phonics(client):
    s = client.get("/api/content").json()
    skills = {k["id"]: k for k in s["skills"]}
    assert skills["literacy.gpc.initial_letter"]["modes"] == ["letters"]
    assert skills["maths.subitising.perceptual"]["stages"] == ["eyfs"]
    assert sum(1 for o in s["objectives"] if o["out_of_scope"]) == 3
    assert s["phonics"][0]["sets"][0]["gpcs"][1] == {"grapheme": "a", "phoneme": "æ", "example": "ant"}


def _attempt(learner: str, seed: int = 1, *, right: bool = True, event_id: str = "e" * 32) -> dict[str, object]:
    from flashtap import rounds

    r = rounds.generate(rounds.Mode.COUNTING, 4, seed)
    option = r.answer if right else next(o.id for o in r.options if not o.correct)
    return {
        "event_id": event_id,
        "learner_id": learner,
        "session_id": "5" * 32,
        "mode": "counting",
        "version": 1,
        "choices": 4,
        "seed": seed,
        "asked": "mixed",
        "presented_at": "2026-11-02T09:00:00Z",
        "answered_at": "2026-11-02T09:00:04Z",
        "first_answer": {"option": option},
        "tries": 1 if right else 2,
        "outcome": "right",
    }


def test_learner_records_over_http(client):
    assert client.get("/api/learners").json() == []
    made = client.post("/api/learners", json={"nickname": "Fox"})
    assert made.status_code == 201
    fox = made.json()["id"]
    assert client.post("/api/learners", json={"nickname": "fox"}).status_code == 409
    assert (
        client.post("/api/learners", json={"nickname": " "}).json()["detail"] == "A nickname needs at least one letter."
    )
    assert client.patch(f"/api/learners/{fox}", json={"nickname": "Red Fox"}).json()["nickname"] == "Red Fox"

    ack = client.post("/api/attempts", json=_attempt(fox, right=False))
    assert ack.json() == {"event_id": "e" * 32, "first_correct": False, "duplicate": False}
    assert client.post("/api/attempts", json=_attempt(fox, right=False)).json()["duplicate"] is True
    assert client.post("/api/attempts", json=_attempt(fox, seed=2)).status_code == 409  # same event id, other contents
    assert client.post("/api/attempts", json={**_attempt(fox), "version": 9}).status_code == 400
    assert client.post("/api/attempts", json=_attempt("0" * 32, event_id="f" * 32)).status_code == 404
    assert client.post("/api/attempts", json={**_attempt(fox), "event_id": "not an id"}).status_code == 422

    profile = client.get(f"/api/learners/{fox}/profile").json()
    assert profile["learner"]["attempts"] == 1
    assert profile["sessions"] == 1
    counting = next(s for s in profile["skills"] if s["skill"] == "maths.counting.objects")
    assert counting["state"] == "introduced"
    assert counting["held"] == 1
    assert counting["title"]
    rows = client.get(f"/api/learners/{fox}/skills/maths.counting.objects/evidence").json()
    assert rows[0]["counted"] is False
    assert rows[0]["why"].startswith("could be ")

    assert client.post(f"/api/attempts/{'e' * 32}/strike", json={"reason": "a sibling"}).status_code == 204
    assert client.post(f"/api/attempts/{'9' * 32}/strike", json={}).status_code == 404
    assert client.get(f"/api/learners/{fox}/profile").json()["struck"] == 1

    exported = client.get(f"/api/learners/{fox}/export")
    assert exported.headers["content-disposition"] == 'attachment; filename="flashtap-red-fox.json"'
    assert exported.json()["events"][0]["struck"] == "a sibling"

    assert client.delete(f"/api/learners/{fox}").status_code == 204
    assert client.get(f"/api/learners/{fox}/profile").status_code == 404
    assert client.get(f"/api/learners/{fox}/skills/x/evidence").status_code == 404
    assert client.get("/api/learners").json() == []


def test_an_export_of_a_nickname_with_no_letters_is_still_named(client):
    odd = client.post("/api/learners", json={"nickname": "★★"}).json()["id"]
    assert client.get(f"/api/learners/{odd}/export").headers["content-disposition"].endswith('"flashtap-learner.json"')


def test_engine_sessions_next_and_replay(client):
    fox = client.post("/api/learners", json={"nickname": "Fox"}).json()["id"]
    client.put("/api/settings", json={"choices": 3, "tries": 1})
    r = client.post("/api/v1/sessions", json={"learner_id": fox})
    assert r.status_code == 201
    s = r.json()
    assert s["policy"] == "utility@1"
    assert s["config"] == {"choices": 3, "tries": 1, "max_rounds": 20, "max_minutes": 15, "break_every": 10}
    n = client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 0}).json()
    assert n["action"] == "round"
    assert n["round"]["choices"] == 3
    assert n["round"]["tries"] == 1
    assert n["rationale"][0] == "placement_probe"
    assert len(n["candidates"]) == 12
    assert client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 0}).json() == n
    assert client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 5}).status_code == 400
    assert client.post(f"/api/v1/sessions/{'f' * 32}/next", json={"seq": 0}).status_code == 404
    assert client.post("/api/v1/sessions", json={"learner_id": "f" * 32}).status_code == 404
    out = client.post("/api/v1/evaluations/replay", json={"learner_id": fox}).json()
    assert (out["decisions"], out["reproduced"], out["differences"]) == (1, 1, [])
    assert client.post("/api/v1/evaluations/replay", json={}).status_code in (400, 422)
    assert client.post("/api/v1/evaluations/replay", json={"policy": "utility@0", "learner_id": fox}).status_code == 400
