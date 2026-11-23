"""Command line: `doctor` checks the environment, `round` prints a round, `content check` and `content list` read the
content packs, `learners list` and `learners rebuild` read the learner records, `openapi` writes the API's schema (the
source of the web app's types), `set` shows or changes a setting, `serve` starts the web server."""

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from strata_python import cli as shared

from flashtap import __version__, content, rounds, settings
from flashtap.learners.report import SkillInfo
from flashtap.server.app import PORT

if TYPE_CHECKING:
    from fastapi import FastAPI


def _create_app() -> "FastAPI":
    from flashtap.server.app import create_app  # here, so the other commands do not build the app

    return create_app()


def run_server(host: str, port: int) -> None:
    from flashtap.server import app as server_app

    server_app.main(["--host", host, "--port", str(port)])


def cmd_round(args: argparse.Namespace) -> int:
    _utf8()
    r = rounds.generate(
        rounds.Mode(args.mode) if args.mode else settings.mode(),
        args.choices or settings.choices(),
        args.seed,
        args.version,
    )
    if args.json:
        print(r.model_dump_json(indent=1))
        return 0
    print(f"{r.prompt}  {r.show}   ({r.mode} v{r.version}, {r.mechanic}, seed {r.seed})")
    if r.say != r.prompt:
        print(f"  said: {r.say}")
    for o in r.options:
        print(f"  {'*' if o.correct else ' '} {o.picture}  {o.word}" + (f"  ({o.distractor})" if o.distractor else ""))
    if r.pieces:
        print("  pieces: " + " ".join(p.picture for p in r.pieces))
    words = {p.id: p.picture for p in r.pieces}
    for s in r.places:
        wanted = "".join(words[k] for k in s.takes)
        print(
            f"  {s.picture or s.word}: {s.holds} of {wanted}"
            if s.holds < len(s.takes)
            else f"  {s.picture or s.word}: {wanted}"
        )
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


def _skills() -> list[SkillInfo]:
    s = content.summarise(content.load(), {m.value: ids for m, ids in rounds.MODE_SKILLS.items()})
    return [SkillInfo(id=k.id, title=k.title, domain=k.domain, strand=k.strand) for k in s.skills]


def cmd_learners_list(args: argparse.Namespace) -> int:
    from sqlalchemy.orm import Session

    from flashtap.learners import db, store

    _utf8()
    engine = db.open_engine()
    with Session(engine) as s:
        rows = store.list_learners(s)
    engine.dispose()
    for x in rows:
        last = x.last_played.date().isoformat() if x.last_played else "never"
        print(f"{x.id}  {x.nickname}  {x.attempts} round(s), last played {last}")
    if not rows:
        print("no learners yet: add one on the Learners screen")
    return 0


def cmd_learners_rebuild(args: argparse.Namespace) -> int:
    """Rebuild the estimates in an export from its events (the PR 4 exit criterion: the log reproduces them exactly).
    Exit 1 and name each difference when it does not."""
    from flashtap.learners import store

    _utf8()
    saved = store.Export.model_validate_json(Path(args.export).read_text(encoding="utf-8"))
    problems = store.rebuild(saved, _skills() if args.current_packs else None)
    for line in problems:
        print(line)
    if problems:
        print(f"{len(problems)} difference(s) rebuilding {len(saved.events)} event(s)")
        return 1
    print(f"ok: {len(saved.events)} event(s) rebuild the {len(saved.skills)} skill estimates exactly")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="flashtap")
    sub = p.add_subparsers(dest="cmd", required=True)
    shared.add_doctor(sub, "flashtap", __version__, ("fastapi", "uvicorn", "pydantic", "strata_python"))
    r = sub.add_parser("round", help="print one round (the same seed prints the same round)")
    r.add_argument("--mode", choices=[m.value for m in rounds.Mode])
    r.add_argument("--choices", type=int, choices=range(rounds.MIN_CHOICES, rounds.MAX_CHOICES + 1))
    r.add_argument("--seed", type=int)
    r.add_argument("--version", type=int, help="the template version to rebuild (only the current one is kept)")
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
    lr = sub.add_parser("learners", help="read the learner records")
    lsub = lr.add_subparsers(dest="learners_cmd", required=True)
    ll = lsub.add_parser("list", help="each learner with the rounds recorded")
    ll.set_defaults(fn=cmd_learners_list)
    rb = lsub.add_parser("rebuild", help="rebuild an export's estimates from its events and compare")
    rb.add_argument("export", help="a file from the Learner screen's Export (GET /api/learners/{id}/export)")
    rb.add_argument("--current-packs", action="store_true", help="report on today's skills, not the export's")
    rb.set_defaults(fn=cmd_learners_rebuild)
    shared.add_openapi(sub, _create_app)  # web/openapi.json, from the repository root; --check in CI
    shared.add_set(sub, settings.SETTINGS)
    shared.add_serve(sub, run_server, default_port=PORT)
    a = p.parse_args(argv)
    return a.fn(a)
