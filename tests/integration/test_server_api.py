"""The HTTP API over a real server on a loopback port (`live_app` from the strata-python plugin)."""

import json
import urllib.request

from flashtap.server.app import create_app


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def test_a_real_server_answers_health_modes_and_rounds(live_app):
    with live_app(create_app()) as base:
        assert _get(f"{base}/api/health")["ok"] is True
        assert len(_get(f"{base}/api/modes")) == 6
        r = _get(f"{base}/api/round?mode=counting&choices=8&seed=99")
        assert len(r["options"]) == 8
        assert _get(f"{base}/api/round?mode=counting&choices=8&seed=99") == r
