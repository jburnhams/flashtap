import pytest
from fastapi.testclient import TestClient
from strata_python.db.web import database

from flashtap import rounds
from flashtap.mechanics import Mode
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
        "missing", "quick_look", "listen", "give", "order", "capitals", "sort_sounds", "sounds", "mixed",
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


def test_a_round_at_a_step_of_difficulty(client):
    r = client.get("/api/round", params={"mode": "counting", "level": 0, "seed": 5}).json()
    assert (r["level"], r["choices"]) == (0, rounds.TEMPLATES[Mode.COUNTING].levels[0].choices)
    assert r == rounds.at_level(Mode.COUNTING, 0, 5).model_dump(mode="json")
    assert client.get("/api/round", params={"mode": "counting", "seed": 5}).json()["level"] is None  # by hand: no step
    both = client.get("/api/round", params={"mode": "counting", "level": 0, "choices": 3})
    assert both.status_code == 400
    assert "level or choices, not both" in both.text
    assert client.get("/api/round", params={"mode": "mixed", "level": 0}).status_code == 400
    assert client.get("/api/round", params={"mode": "counting", "level": 4}).status_code == 400


def test_an_attempt_at_a_step_is_judged_on_the_round_at_that_step(client):
    fox = client.post("/api/learners", json={"nickname": "Fox"}).json()["id"]
    r = rounds.at_level(Mode.MISSING, 2, 9)
    attempt = {
        "event_id": "a" * 32,
        "learner_id": fox,
        "session_id": "b" * 32,
        "mode": "missing",
        "version": r.version,
        "content": r.content,
        "choices": r.choices,
        "seed": r.seed,
        "level": 2,
        "asked": "missing",
        "presented_at": "2026-11-02T09:00:00Z",
        "answered_at": "2026-11-02T09:00:04Z",
        "first_answer": {"option": r.answer},
        "tries": 1,
        "outcome": "right",
    }
    assert client.post("/api/attempts", json={**attempt, "level": 0}).status_code == 400  # step 0 lays out 3, not 4
    assert client.post("/api/attempts", json=attempt).json()["first_correct"] is True
    assert client.post("/api/attempts", json={**attempt, "level": 1}).status_code == 409  # the same event, changed
    log = client.get(f"/api/learners/{fox}/export").json()
    assert log["format"] == "flashtap-learner@6"
    assert [e["level"] for e in log["events"]] == [2]


@pytest.mark.parametrize("params", [{"choices": 9}, {"choices": 1}, {"mode": "spelling"}, {"seed": -1}, {"version": 0}])
def test_bad_round_queries_are_refused(client, params):
    assert client.get("/api/round", params=params).status_code == 422


def test_rounds_to_keep_come_several_at_once_each_rebuildable(client):
    assert client.put("/api/settings", json={"mode": "counting", "choices": "3", "tries": "2"}).status_code == 200
    kept = client.get("/api/rounds", params={"count": 5}).json()
    assert len(kept) == 5
    assert {r["mode"] for r in kept} == {"counting"}
    assert {(r["choices"], r["tries"]) for r in kept} == {(3, 2)}
    assert len({r["seed"] for r in kept}) > 1  # fresh seeds, not one round five times
    for r in kept:  # each is the round its (mode, version, choices, seed, content) rebuild, so it can be judged later
        again = rounds.generate(Mode(r["mode"]), r["choices"], r["seed"], r["version"], r["content"]).model_dump(
            mode="json"
        )
        assert {**again, "tries": r["tries"]} == r
    mixed = client.get("/api/rounds", params={"mode": "mixed", "count": 3, "choices": 4}).json()
    assert all(r["mode"] != "mixed" and r["choices"] == 4 for r in mixed)
    assert len(client.get("/api/rounds").json()) == 8


@pytest.mark.parametrize("params", [{"count": 0}, {"count": 21}, {"mode": "spelling"}, {"choices": 9}])
def test_bad_queries_for_rounds_to_keep_are_refused(client, params):
    assert client.get("/api/rounds", params=params).status_code == 422


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
        "session_rounds": 20,
        "session_minutes": 15,
        "break_every": 10,
        "choice_every": 5,
        "rate_every": 4,
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
    fresh = _attempt(fox, event_id="1" * 32)  # a new event: a used id is checked against its log entry first
    assert client.post("/api/attempts", json={**fresh, "version": 9}).status_code == 400
    # A round served from packs the server no longer has is refused, not judged against today's round.
    stale = client.post("/api/attempts", json={**fresh, "content": {**rounds.content_of(Mode.COUNTING), "words": 0}})
    assert stale.status_code == 400
    assert "words@0" in stale.json()["detail"]
    # A retry of a logged event is matched against what was logged, packs included, without rebuilding the round.
    served = {**_attempt(fox, right=False), "content": rounds.content_of(Mode.COUNTING)}
    assert client.post("/api/attempts", json=served).json()["duplicate"] is True
    assert client.post("/api/attempts", json={**served, "content": {"words": 0}}).status_code == 409
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
    assert s["policy"] == "utility@5"
    assert s["config"] == {
        "choices": 3,
        "tries": 1,
        "max_rounds": 20,
        "max_minutes": 15,
        "break_every": 10,
        "choice_every": 5,
        "rate_every": 4,
    }
    n = client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 0}).json()
    assert n["action"] == "round"
    # the engine sets the step of difficulty (the easiest, knowing nothing yet), not the grown-up's 3 choices
    assert n["round"]["level"] == 0
    assert n["round"]["choices"] == rounds.TEMPLATES[Mode(n["round"]["mode"])].levels[0].choices
    assert n["round"]["tries"] == 1
    assert n["rationale"][0] == "placement_probe"
    assert len(n["candidates"]) == len(rounds.PLAYABLE)  # one candidate per kind of round
    assert client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 0}).json() == n
    assert client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 5}).status_code == 400
    assert client.post(f"/api/v1/sessions/{'f' * 32}/next", json={"seq": 0}).status_code == 404
    assert client.post("/api/v1/sessions", json={"learner_id": "f" * 32}).status_code == 404
    out = client.post("/api/v1/evaluations/replay", json={"learner_id": fox}).json()
    assert (out["decisions"], out["reproduced"], out["differences"]) == (1, 1, [])
    assert client.post("/api/v1/evaluations/replay", json={}).status_code in (400, 422)
    assert client.post("/api/v1/evaluations/replay", json={"policy": "utility@0", "learner_id": fox}).status_code == 400


def test_choices_picks_ratings_and_overrides_over_http(client):
    fox = client.post("/api/learners", json={"nickname": "Fox"}).json()["id"]
    client.put("/api/settings", json={"choice_every": 1, "rate_every": 1, "session_rounds": 3})
    s = client.post("/api/v1/sessions", json={"learner_id": fox}).json()
    n = client.post(f"/api/v1/sessions/{s['id']}/next", json={"seq": 0}).json()
    assert (n["action"], n["round"], n["picked"], n["rate"]) == ("choice", None, None, True)
    assert [o["round"]["mode"] for o in n["offers"]] == [o["mode"] for o in n["offers"]]
    picked = client.post(f"/api/v1/sessions/{s['id']}/decisions/0/pick", json={"offer": 1})
    assert picked.status_code == 200
    p = picked.json()
    assert (p["picked"], p["round"]) == (1, n["offers"][1]["round"])
    assert client.post(f"/api/v1/sessions/{s['id']}/decisions/0/pick", json={"offer": 0}).status_code == 409
    assert client.post(f"/api/v1/sessions/{s['id']}/decisions/0/pick", json={"offer": 2}).status_code == 422
    assert client.post(f"/api/v1/sessions/{s['id']}/decisions/9/pick", json={"offer": 0}).status_code == 404
    r = p["round"]
    first = (
        {"option": r["answer"]}
        if r["options"]
        else {"placement": {k: pl["id"] for pl in r["places"] for k in pl["takes"][: pl["holds"]]}}
    )
    attempt = {
        "event_id": "e" * 32,
        "learner_id": fox,
        "session_id": s["id"],
        "decision_id": p["id"],
        "mode": r["mode"],
        "version": r["version"],
        "content": r["content"],
        "choices": r["choices"],
        "seed": r["seed"],
        "level": r["level"],
        "asked": "next",
        "presented_at": "2026-11-02T09:00:00Z",
        "answered_at": "2026-11-02T09:00:04Z",
        "first_answer": first,
        "tries": 1,
        "outcome": "right",
    }
    assert client.post("/api/attempts", json=attempt).json()["first_correct"] is True
    rating = client.post(f"/api/attempts/{'e' * 32}/rating", json={"value": 1})
    assert rating.json() == {"event_id": "e" * 32, "scale": "enjoyment", "value": 1, "duplicate": False}
    assert client.post(f"/api/attempts/{'e' * 32}/rating", json={"value": -1}).status_code == 409
    assert client.post(f"/api/attempts/{'e' * 32}/rating", json={"value": 2}).status_code == 422
    assert client.post(f"/api/attempts/{'f' * 32}/rating", json={"value": 0}).status_code == 404

    skill = "maths.counting.objects"
    made = client.post(f"/api/v1/learners/{fox}/overrides", json={"skill": skill, "says": "can", "observer": "parent"})
    assert made.status_code == 201
    told = made.json()
    assert (told["says"], told["observer"], told["note"], told["withdrawn_at"]) == ("can", "parent", "", None)
    bad = {"skill": "maths.flying", "says": "can", "observer": "parent"}
    assert client.post(f"/api/v1/learners/{fox}/overrides", json=bad).status_code == 400
    assert (
        client.post(f"/api/v1/learners/{fox}/overrides", json={**bad, "skill": skill, "says": "maybe"}).status_code
        == 422
    )
    profile = client.get(f"/api/learners/{fox}/profile").json()
    counting = next(x for x in profile["skills"] if x["skill"] == skill)
    assert counting["told"]["id"] == told["id"]
    kinds = {k["mode"]: k for k in profile["engagement"]["kinds"]}
    assert kinds[r["mode"]]["liked"] == 1
    assert kinds[r["mode"]]["picked"] == 1
    w = client.post(f"/api/v1/learners/{fox}/overrides/{told['id']}/withdraw")
    assert w.status_code == 204
    assert client.post(f"/api/v1/learners/{fox}/overrides/{'f' * 32}/withdraw").status_code == 404
    profile = client.get(f"/api/learners/{fox}/profile").json()
    assert next(x for x in profile["skills"] if x["skill"] == skill)["told"] is None
    out = client.post("/api/v1/evaluations/replay", json={"learner_id": fox}).json()
    assert (out["reproduced"], out["differences"]) == (out["decisions"], [])
    export = client.get(f"/api/learners/{fox}/export").json()
    assert export["format"] == "flashtap-learner@6"
    assert len(export["ratings"]) == 1
    assert len(export["overrides"]) == 1


def test_voice_lists_sounds_and_takes_a_recording_of_one(client):
    from strata_python.testing import sine_wav

    out = client.get("/api/v1/voice").json()
    assert out["clips"] == {}
    assert len(out["sounds"]) == 45
    sh = next(x for x in out["sounds"] if x["line"] == "/ʃ/")
    assert sh == {**sh, "graphemes": ["sh"], "clip": None, "source": None, "vowel": False}

    wav = sine_wav(0.8, rate=24000)
    put = client.put("/api/v1/voice/recordings", params={"line": "/ʃ/"}, content=wav)
    assert put.status_code == 200
    assert put.json()["source"] == "recorded"
    url = client.get("/api/v1/voice").json()["clips"]["/ʃ/"]
    assert url == put.json()["clip"]
    assert url.startswith("api/v1/voice/clips/")
    got = client.get("/" + url)
    assert got.content == wav
    assert got.headers["content-type"] == "audio/wav"
    assert "immutable" in got.headers["cache-control"]

    assert client.delete("/api/v1/voice/recordings", params={"line": "/ʃ/"}).status_code == 204
    assert client.delete("/api/v1/voice/recordings", params={"line": "/ʃ/"}).status_code == 404
    assert client.get("/" + url).status_code == 404  # a clip no line holds is not served
    assert client.get("/api/v1/voice/clips/manifest.json").status_code == 404


def test_voice_refuses_a_line_that_is_not_a_sound_and_a_file_that_is_not_a_wav(client):
    from strata_python.testing import sine_wav

    not_sound = client.put("/api/v1/voice/recordings", params={"line": "Listen."}, content=sine_wav(0.5, rate=24000))
    assert not_sound.status_code == 400
    assert "only sounds" in not_sound.json()["detail"]
    bad = client.put("/api/v1/voice/recordings", params={"line": "/m/"}, content=b"not a wav")
    assert bad.status_code == 400
    long = client.put("/api/v1/voice/recordings", params={"line": "/m/"}, content=sine_wav(11, rate=24000))
    assert long.status_code == 400
    assert client.get("/api/v1/voice").json()["clips"] == {}
