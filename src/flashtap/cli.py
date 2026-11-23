"""Command line: `doctor` checks the environment, `round` prints a round, `content check` and `content list` read the
content packs, `set` shows or changes a setting, `serve` starts the web server."""

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from strata_python import cli as shared

from flashtap import __version__, content, rounds, settings
from flashtap.server.app import PORT


def run_server(host: str, port: int) -> None:
    from flashtap.server import app as server_app

    server_app.main(["--host", host, "--port", str(port)])


def cmd_round(args: argparse.Namespace) -> int:
    _utf8()
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


def _utf8() -> None:
    # Pictures and IPA: a Windows console's default code page (cp1252) cannot print them, so write UTF-8.
    out = sys.stdout
    if isinstance(out, io.TextIOWrapper):
        cast("io.TextIOWrapper[Any]", out).reconfigure(encoding="utf-8")


def cmd_content_check(args: argparse.Namespace) -> int:
    """Exit 1 and name every problem when the packs break a rule (CI runs this; the server refuses to start too)."""
    _utf8()
    r, problems = content.build(Path(args.packs) if args.packs else content.PACKS)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} problem(s) in {len(r.packs)} pack(s)")
        return 1
    mapped = sum(1 for o in r.objectives.values() if o.skills)
    print(
        f"ok: {len(r.packs)} packs, {len(r.skills)} skills, {len(r.edges)} edges, {len(r.misconceptions)} misconceptions, "
        f"{len(r.gpcs())} GPCs, {len(r.words)} words; {len(r.objectives)} objectives "
        f"({mapped} mapped, {len(r.objectives) - mapped} out of scope)"
    )
    return 0


def cmd_content_list(args: argparse.Namespace) -> int:
    _utf8()
    s = content.summarise(content.load(), {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})
    if args.json:
        print(s.model_dump_json(indent=1))
        return 0
    strand = ""
    for k in sorted(s.skills, key=lambda k: (k.domain, k.strand)):
        if k.strand != strand:
            strand = k.strand
            print(f"{k.domain} / {strand}")
        tags = ", ".join([*k.stages, *(f"played in {m}" for m in k.modes)])
        print(f"  {k.id}  {k.title}" + (f"  ({tags})" if tags else ""))
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
    c = sub.add_parser("content", help="check or list the content packs")
    csub = c.add_subparsers(dest="content_cmd", required=True)
    ck = csub.add_parser("check", help="find dangling edges, cycles, unmapped objectives and other pack errors")
    ck.add_argument("--packs", help="a folder of *.toml packs to check instead of the packaged ones")
    ck.set_defaults(fn=cmd_content_check)
    ls = csub.add_parser("list", help="print the skills by domain and strand")
    ls.add_argument("--json", action="store_true", help="the API's shape (GET /api/content)")
    ls.set_defaults(fn=cmd_content_list)
    shared.add_set(sub, settings.SETTINGS)
    shared.add_serve(sub, run_server, default_port=PORT)
    a = p.parse_args(argv)
    return a.fn(a)
