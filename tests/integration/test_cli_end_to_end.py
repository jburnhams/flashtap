"""The CLI end-to-end: in this process and as a real `python -m flashtap` process."""

import json


def test_entry_point_runs_as_a_module(cli_subprocess):
    r = cli_subprocess("round", "--mode", "colours", "--seed", "42", "--json")
    assert json.loads(r.stdout)["prompt"].startswith("Which one is ")
    assert "flashtap" in cli_subprocess("doctor").stdout


def test_a_setting_changed_from_the_cli_reaches_the_api(cli, client):
    cli("set", "mode", "letters")
    assert client.get("/api/round").json()["mode"] == "letters"
    assert cli("set", "mode", "default").stdout.startswith(
        "mode = mixed  (one of: matching, "
    )  # `set` lists the choices
    assert cli("set", "choices", "20", check=False).code != 0


def test_content_check_as_a_process_reads_the_packaged_packs(cli_subprocess, tmp_path):
    assert cli_subprocess("content", "check").stdout.startswith("ok: 8 packs")
    (tmp_path / "cycle.toml").write_text(
        'pack = "cycle"\nversion = 1\ntitle = "Cycle"\nstatus = "draft"\n'
        '[[sources]]\nid = "s.x"\ntitle = "S"\nurl = "https://example.com"\n'
        '[[domains]]\nid = "d"\ntitle = "D"\n[[strands]]\nid = "d.s"\ndomain = "d"\ntitle = "S"\n'
        '[[skills]]\nid = "d.a"\ntitle = "A"\nstrand = "d.s"\n'
        'edges = [{ relation = "prerequisite_strong", from = "d.b", confidence = "low", source = "s.x" }]\n'
        '[[skills]]\nid = "d.b"\ntitle = "B"\nstrand = "d.s"\n'
        'edges = [{ relation = "prerequisite_strong", from = "d.a", confidence = "low", source = "s.x" }]\n',
        encoding="utf-8",
    )
    r = cli_subprocess("content", "check", "--packs", str(tmp_path), check=False)
    assert r.code == 1
    assert "prerequisite_strong cycle: d.a -> d.b -> d.a" in r.stdout


def test_voice_build_makes_clips_through_strata_models_and_the_app_serves_them(cli, client, fake_models, tmp_path):
    """`flashtap voice build` against the strata-models stand-in over real HTTP: each job writes a real WAV where the
    service would, the store keeps it, and the API serves it. A consonant sound is listed to record, never asked for."""
    from strata_python.testing import sine_wav

    def speak(params: dict[str, object]) -> dict[str, object]:
        path = tmp_path / f"tts-{len(fake_models.jobs)}.wav"
        path.write_bytes(sine_wav(0.4, rate=24000))
        return {"path": str(path), "voice": params["voice"], "duration_s": 0.4}

    fake_models.results["speak"] = speak
    fake_models.models["speak"] = "kokoro-v1"
    r = cli("voice", "build", "--only", "sounds", "--limit", "33")  # /s/ ... /eɪ/, /iː/, /aɪ/: consonants and vowels
    asked = [j["params"] for j in fake_models.jobs]
    assert all(p.get("phonemes") for p in asked)
    assert {p["voice"] for p in asked} == {"bf_emma"}
    assert {p["text"] for p in asked} >= {"/æ/", "/ɪ/", "/eɪ/"}
    assert "/ʃ/" not in {p["text"] for p in asked}
    assert f"made {len(asked)}, kept 0, failed 0;" in r.stdout
    assert "sounds to record in the app" in r.stdout

    voice = client.get("/api/v1/voice").json()
    a = next(s for s in voice["sounds"] if s["line"] == "/æ/")
    assert a["source"] == "generated"
    assert client.get("/" + a["clip"]).content == sine_wav(0.4, rate=24000)
    assert "sentences: 0 of" in cli("voice", "status").stdout
    assert cli("voice", "build", "--only", "sounds", "--limit", "33").stdout.startswith("made 0, kept")  # nothing again
    # the speak role's model changes on the service: every made clip is made again, read from its registry
    fake_models.models["speak"] = "kokoro-v2"
    assert f"made {len(asked)}, kept 0," in cli("voice", "build", "--only", "sounds", "--limit", "33").stdout
    assert cli("voice", "lines", "--missing").stdout.count("missing") > 1000


def test_voice_build_says_which_lines_failed(cli, fake_models):
    fake_models.fail("CUDA out of memory", role="speak")
    r = cli("voice", "build", "--only", "sentences", "--limit", "2", check=False)
    # the first job fails; the next "succeeds" with the stand-in's default answer, a WAV path that is not there
    assert r.code == 1
    assert "FAILED 0: CUDA out of memory" in r.stdout
    assert "No such file" in r.stdout
    assert "made 0, kept 0, failed 2;" in r.stdout
