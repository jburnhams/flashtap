"""Command line: `doctor` checks the environment, `round` prints a round, `set` shows or changes a setting, `serve` starts the web server."""

import argparse
import io
import sys
from collections.abc import Sequence
from typing import Any, cast

from strata_python import cli as shared

from flashtap import __version__, rounds, settings
from flashtap.server.app import PORT


def run_server(host: str, port: int) -> None:
    from flashtap.server import app as server_app

    server_app.main(["--host", host, "--port", str(port)])


def cmd_round(args: argparse.Namespace) -> int:
    # Pictures are emoji: a Windows console's default code page (cp1252) cannot print them, so write UTF-8.
    out = sys.stdout
    if isinstance(out, io.TextIOWrapper):
        cast("io.TextIOWrapper[Any]", out).reconfigure(encoding="utf-8")
    r = rounds.generate(
        rounds.Mode(args.mode) if args.mode else settings.mode(), args.choices or settings.choices(), args.seed
    )
    if args.json:
        print(r.model_dump_json(indent=1))
        return 0
    print(f"{r.prompt}  {r.show}   ({r.mode}, seed {r.seed})")
    for o in r.options:
        print(f"  {'*' if o.correct else ' '} {o.picture}  {o.word}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="flashtap")
    sub = p.add_subparsers(dest="cmd", required=True)
    shared.add_doctor(sub, "flashtap", __version__, ("fastapi", "uvicorn", "pydantic", "strata_python"))
    r = sub.add_parser("round", help="print one round (the same seed prints the same round)")
    r.add_argument("--mode", choices=[m.value for m in rounds.Mode])
    r.add_argument("--choices", type=int, choices=range(rounds.MIN_CHOICES, rounds.MAX_CHOICES + 1))
    r.add_argument("--seed", type=int)
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_round)
    shared.add_set(sub, settings.SETTINGS)
    shared.add_serve(sub, run_server, default_port=PORT)
    a = p.parse_args(argv)
    return a.fn(a)
