"""The CLI end-to-end: in this process and as a real `python -m flashtap` process."""

import json


def test_entry_point_runs_as_a_module(cli_subprocess):
    r = cli_subprocess("round", "--mode", "colours", "--seed", "42", "--json")
    assert json.loads(r.stdout)["prompt"].startswith("Which one is ")
    assert "flashtap" in cli_subprocess("doctor").stdout


def test_a_setting_changed_from_the_cli_reaches_the_api(cli, client):
    cli("set", "mode", "letters")
    assert client.get("/api/round").json()["mode"] == "letters"
    assert cli("set", "mode", "default").stdout.strip() == "mode = mixed"
    assert cli("set", "choices", "20", check=False).code != 0


def test_content_check_as_a_process_reads_the_packaged_packs(cli_subprocess, tmp_path):
    assert cli_subprocess("content", "check").stdout.startswith("ok: 7 packs")
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
