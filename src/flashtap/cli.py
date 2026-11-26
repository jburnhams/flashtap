"""Command line: `doctor` checks the environment, `round` prints a round, `content check` and `content list` read the
content packs, `learners list` and `learners rebuild` read the learner records, `engine simulate` runs the adaptive
engine on simulated learners, `voice lines`, `voice status` and `voice build` list and make the recorded voice, `openapi` writes the API's schema (the
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

    from flashtap.learners import store


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
    same, remade = _replay(saved)
    for line in [*problems, *remade]:
        print(line)
    if problems or remade:
        print(
            f"{len(problems) + len(remade)} difference(s) rebuilding {len(saved.events)} event(s) and {len(saved.decisions)} decision(s)"
        )
        return 1
    print(f"ok: {len(saved.events)} event(s) rebuild the {len(saved.skills)} skill estimates exactly")
    if saved.decisions:
        print(f"ok: {same} engine decision(s) remade exactly")
    return 0


def _replay(saved: "store.Export") -> tuple[int, list[str]]:
    from flashtap.engine import model, replay

    starts = {x.id: (x.started_at, x.config) for x in saved.sessions}
    return replay.replay(saved.events, saved.decisions, starts, model.graph())


def cmd_engine_simulate(args: argparse.Namespace) -> int:
    """The plan's exit test (PR 5): exit 1 when the engine's model does not beat the rule baseline on held-out learners."""
    from flashtap.engine import simulate

    r = simulate.report(args.learners, args.sessions, args.seed)
    if args.json:
        print(r.model_dump_json(indent=1))
    else:
        for line in simulate.describe(r):
            print(line)
    return 0 if r.beats_rule else 1


def voice_default() -> str:
    from flashtap.voice import DEFAULT_VOICE

    return DEFAULT_VOICE


def cmd_voice_lines(args: argparse.Namespace) -> int:
    from flashtap import voice

    _utf8()
    have = voice.Store(voice.home()).read().clips
    for line in voice.lines():
        c = have.get(line)
        if args.missing and c is not None:
            continue
        print(f"{c.source if c else 'missing':9}  {line}")
    return 0


def cmd_voice_status(args: argparse.Namespace) -> int:
    from flashtap import voice

    _utf8()
    store = voice.Store(voice.home())
    have = store.read().clips
    wanted = voice.lines()
    sentences = [x for x in wanted if voice.phoneme_of(x) is None]
    sounds = [x for x in wanted if voice.phoneme_of(x) is not None]
    print(f"voice clips in {store.root}")
    print(f"  sentences: {sum(x in have for x in sentences)} of {len(sentences)} have a clip")
    print(f"  sounds:    {sum(x in have for x in sounds)} of {len(sounds)} have a clip")
    to_record = [x for x in sounds if x not in have and not voice.is_vowel(voice.phoneme_of(x) or "")]
    if to_record:
        print(f"  to record in the app (Sounds screen): {' '.join(to_record)}")
    voices = sorted({c.voice for c in have.values()})
    if voices:
        print(f"  voices: {', '.join(voices)}")
    return 0


def cmd_voice_build(args: argparse.Namespace) -> int:
    from flashtap import voice

    _utf8()
    store = voice.Store(voice.home())
    wanted = voice.lines()
    if args.only == "sounds":
        wanted = [x for x in wanted if voice.phoneme_of(x) is not None]
    elif args.only == "sentences":
        wanted = [x for x in wanted if voice.phoneme_of(x) is None]
    if args.limit:
        wanted = wanted[: args.limit]
    r = voice.build(
        store,
        wanted,
        voice=args.voice,
        model=args.model,
        force=args.force,
        now=voice.speak_settings(args.model),
        say=print,
    )
    print(
        f"made {len(r.made)}, kept {len(r.kept)}, failed {len(r.failed)}; {len(r.to_record)} sounds to record in the app"
    )
    return 1 if r.failed else 0


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
    en = sub.add_parser("engine", help="the adaptive engine")
    esub = en.add_subparsers(dest="engine_cmd", required=True)
    sm = esub.add_parser(
        "simulate", help="simulated learners: held-out log loss of each model, skills learnt per policy"
    )
    sm.add_argument("--learners", type=int, default=200, help="how many (at least 4; 30%% are held out)")
    sm.add_argument("--sessions", type=int, default=6, help="sessions each, one to three days apart")
    sm.add_argument("--seed", type=int, default=1)
    sm.add_argument("--json", action="store_true")
    sm.set_defaults(fn=cmd_engine_simulate)
    vo = sub.add_parser("voice", help="the recorded voice: what Flashtap says, and its clips")
    vsub = vo.add_subparsers(dest="voice_cmd", required=True)
    vl = vsub.add_parser("lines", help="every line Flashtap says, with its clip's source or 'missing'")
    vl.add_argument("--missing", action="store_true", help="only the lines with no clip")
    vl.set_defaults(fn=cmd_voice_lines)
    vs = vsub.add_parser("status", help="how many lines have clips, and the sounds still to record")
    vs.set_defaults(fn=cmd_voice_status)
    vb = vsub.add_parser("build", help="make the missing clips with strata-models (role speak)")
    vb.add_argument(
        "--voice", default=voice_default(), help="the Kokoro voice (default %(default)s; UK voices start b)"
    )
    vb.add_argument("--model", default=None, help="a strata-models model other than the speak role's")
    vb.add_argument("--force", action="store_true", help="remake made clips (never a recording)")
    vb.add_argument("--only", choices=("sounds", "sentences"), default=None)
    vb.add_argument("--limit", type=int, default=0, help="at most this many lines (a first listen)")
    vb.set_defaults(fn=cmd_voice_build)
    shared.add_openapi(sub, _create_app)  # web/openapi.json, from the repository root; --check in CI
    shared.add_set(sub, settings.SETTINGS)
    shared.add_serve(sub, run_server, default_port=PORT)
    a = p.parse_args(argv)
    return a.fn(a)
