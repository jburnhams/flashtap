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
