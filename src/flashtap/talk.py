"""Talk: the lines around a round, varied and with the learner's name, written ahead of time so they are ready to say.

The owner asked for the voice to be more engaging and less repetitive, "using the player name", written by a language
model "in advance so ready" (2026-11-27). Every right answer opened "Yes!", every miss ended "Try again.", and a new
kind of round started with no word that it had changed. So each of those moments has a pool of lines here:

- **Moments** (`MOMENTS`): `right` opens the reply to a right answer in place of "Yes!" (the round's own sentence
  follows: "Brilliant, Fox! There are 5 ducks."), `retry` takes the place of "Try again.", `missed` comes before the
  answer is shown, `start` opens a visit, `pick` asks for a choice of two and `break` offers one. `intro.<kind>` says a
  new kind of round is coming, for every kind there is: the engine chooses the next kind from the learner's answers as
  they come, so no plan is fixed ahead, but every kind it can choose has its lines ready before it is chosen.
- **Writing** (`write`): strata-models' `write` role (a cloud model; strata-models `models.toml`), one call per moment
  with a JSON schema, run on the job queue (`jobs.py`, `talk_write`) at every start until each pool is full. The name
  is never sent: the model writes `{name}` where it goes, and the server fills in the nickname (`pools`), so a
  learner's nickname stays on the server and in the local speech model alone (AGENTS.md rule 8).
- **Checking** (`check`): a written line is kept only if it is short, has no numbers (it would state an answer), no
  word that judges the learner or names a gender, and fits its moment (a question only where the moment asks one).
  The owner can strike any line (`flashtap talk strike`); a struck line is never kept again.
- **Saying** (`pools`, `GET /api/v1/learners/{id}/talk`): each moment's fixed line first, then the written ones with the
  nickname filled in. The web app (`web/src/talk.ts`) goes round each pool so a line comes back only after the rest.
  Every line is voiced by the voice build (`voice.py` `wanted`), for each learner's nickname, so the clips are made
  before play needs them; a line with no clip yet is said by the browser, as before.

The written lines are kept in `~/.flashtap/voice/talk.json` beside the clips, never in git.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from strata_python import files, oslib
from strata_python.contracts import ApiModel

from flashtap import rounds

APP = "flashtap"
ROLE = "write"  # strata-models: "write new short texts to a brief ... a JSON list through `schema`"
POOL = 8  # written lines a moment aims for: with the fixed one, a line comes back about every ninth time
NAME = "{name}"


@dataclass(frozen=True)
class Moment:
    fixed: str  # what is said with no written line (and what was said before 0.17.0)
    brief: str  # what the line is for, for the model
    question: bool = False  # the line asks: it ends with "?"


MOMENTS: dict[str, Moment] = {
    "right": Moment(
        "Yes!",
        "Said the moment a right answer is tapped, before a sentence that says what was right (so never say what was"
        " found). Short and pleased: 'Brilliant!', 'You got it, {name}!'.",
    ),
    "retry": Moment(
        "Try again.",
        "Said after a picture that was not the answer, when another go is left. Calm and encouraging, asking for one"
        " more go; never say how close it was, and never call it wrong.",
    ),
    "missed": Moment(
        "Good try.",
        "Said after the last go, just before the right answer is shown. Kind and matter of fact, never sad: the"
        " learner has done nothing bad.",
    ),
    "start": Moment(
        "Let's play.",
        "The first thing said in a visit, before the first round. A warm hello and a start, not a question.",
    ),
    "pick": Moment(
        "Which one next?",
        "Asks the learner to choose which of two games to play next (their names are said after it). A question.",
        question=True,
    ),
    "break": Moment(
        "Time for a break?",
        "Offers a rest after a run of rounds; the learner may keep playing. A gentle question, never a push either way.",
        question=True,
    ),
}


def intro_key(mode: rounds.Mode) -> str:
    return f"intro.{mode.value}"


def _intro(mode: rounds.Mode) -> Moment:
    t = rounds.TEMPLATES[mode]
    return Moment(
        "",  # nothing was said before: a new kind is introduced only by a written line
        f"Said when a new kind of round is about to start: '{t.name}', where the learner will {t.description[0].lower()}"
        f"{t.description[1:].rstrip('.')}. Says what is coming, simply, not a question, never the answer of a round.",
    )


def moments() -> dict[str, Moment]:
    """Every moment with a pool: the fixed ones, then an intro for every kind of round."""
    return {**MOMENTS, **{intro_key(m): _intro(m) for m in rounds.PLAYABLE}}


# ---- checking a written line ----------------------------------------------------------------------------------------

MAX_WORDS = 9  # said before or after a round's own sentence: a long one holds the learner up
MAX_CHARS = 60
_ALLOWED = re.compile(r"^[A-Za-z ,.!?'’-]+$")
# Words that judge the learner, compare them, promise something the app does not do, or guess a gender. A written
# line is refused for any of them; the fixed lines use none.
_BANNED = frozenset(
    [
        "wrong",
        "bad",
        "fail",
        "failed",
        "failing",
        "stupid",
        "silly",
        "dumb",
        "easy",
        "hard",
        "lose",
        "lost",
        "loser",
        "sorry",
        "oops",
        "idiot",
        "baby",
        "boy",
        "girl",
        "boys",
        "girls",
        "he",
        "she",
        "him",
        "her",
        "his",
        "hers",
        "mum",
        "dad",
        "mummy",
        "daddy",
        "old",
        "age",
        "years",
        "big",
        "little",
        "clever",
        "smart",
        "genius",
        "perfect",
        "perfectly",
        "always",
        "never",
        "next-time",
        "tomorrow",
        "later",
        "prize",
        "reward",
        "sticker",
    ]
)


def check(key: str, line: str) -> str | None:
    """Why `line` cannot be said at `key`, or None when it can."""
    m = moments().get(key)
    if m is None:
        return f"no moment {key}"
    s = line.strip()
    if s.count(NAME) > 1:
        return "the name more than once"
    bare = s.replace(NAME, "Name")
    if "{" in bare or "}" in bare:
        return "a placeholder other than {name}"
    if not bare or len(bare) > MAX_CHARS:
        return f"not 1 to {MAX_CHARS} characters"
    if not _ALLOWED.match(bare):
        return "a character other than letters and punctuation (numbers would state an answer)"
    words = re.findall(r"[A-Za-z'’-]+", bare)
    if len(words) > MAX_WORDS:
        return f"more than {MAX_WORDS} words"
    hit = next((w for w in words if w.lower().strip("'’-") in _BANNED), None)
    if hit is not None:
        return f"the word {hit!r}"
    if bare[-1] not in ".!?":
        return "no full stop, exclamation or question mark at the end"
    if m.question != bare.endswith("?"):
        return "a question where none is asked" if bare.endswith("?") else "not a question"
    if "?" in bare[:-1]:
        return "a question inside it"
    return None


# ---- the store ------------------------------------------------------------------------------------------------------


class Written(BaseModel):
    text: str  # with {name} where the nickname goes
    model: str = ""  # what wrote it
    made: str  # ISO date and time


class Book(BaseModel):
    version: int = 1
    lines: dict[str, list[Written]] = {}
    struck: list[str] = []  # struck by the owner: never kept again


@dataclass
class Store:
    root: Path  # voice.home(): beside the clips

    @property
    def path(self) -> Path:
        return self.root / "talk.json"

    def read(self) -> Book:
        try:
            return Book.model_validate_json(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Book()

    def edit(self, change: Callable[[Book], None]) -> Book:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".talk.lock").open("a+") as lock, oslib.file_lock(lock):
            b = self.read()
            change(b)
            files.write_text_atomic(self.path, b.model_dump_json(indent=1))
            return b

    def strike(self, text: str) -> int:
        """Strike a written line (as written, with {name}, or as said with any nickname in it is not matched): the
        number of moments it was taken from."""
        n = 0

        def change(b: Book) -> None:
            nonlocal n
            for key, pool in b.lines.items():
                kept = [w for w in pool if w.text != text]
                n += len(pool) - len(kept)
                b.lines[key] = kept
            if text not in b.struck:
                b.struck.append(text)

        self.edit(change)
        return n


# ---- writing --------------------------------------------------------------------------------------------------------

SYSTEM = (
    "You write short lines spoken aloud by a calm, warm British voice in a picture game for early learners, who tap"
    " pictures to practise early maths, reading and listening skills. British English and spelling. Plain, friendly"
    " words a young learner knows; no emoji, no numbers, no slang, no sarcasm, no pressure, no praise of the learner"
    " as a person (praise what they did). Never call an answer wrong or bad, never compare the learner with anyone,"
    " never promise a reward, and never guess the learner's gender: use {name} or 'you'. Write {name} exactly,"
    " in about a third of the lines, where the learner's name is said; never more than once in a line. Each line at"
    f" most {MAX_WORDS} words, and each one different from the others in its words, not only its punctuation."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
    "additionalProperties": False,
}

Ask = Callable[
    [str, dict[str, Any]], dict[str, Any]
]  # (prompt, params) -> the write role's result: {text, json, model}


class Answer(BaseModel):
    lines: list[str]  # SCHEMA's one key: a missing or mistyped one fails the moment, named in `failed`


def _ask_default(prompt: str, params: dict[str, Any]) -> dict[str, Any]:
    from strata_python.clients import models

    return models.ask(prompt, APP, role=ROLE, **params)


def prompt_for(key: str, have: Iterable[str], n: int) -> str:
    m = moments()[key]
    taken = [*have, *([m.fixed] if m.fixed else [])]
    avoid = f" Not these, which are already said: {'; '.join(taken)}." if taken else ""
    return f"Write {n} lines. {m.brief}{avoid} Answer with the lines in `lines`."


class Wrote(BaseModel):
    added: dict[str, int] = {}
    full: list[str] = []  # already had a full pool
    refused: dict[str, list[str]] = {}  # key -> "line: why", for the log
    failed: dict[str, str] = {}
    left: list[str] = []


def write(
    store: Store,
    keys: Iterable[str] | None = None,
    *,
    ask: Ask = _ask_default,
    say: Callable[[str], None] = lambda _: None,
    stop: Callable[[], bool] = lambda: False,
) -> Wrote:
    """Fill each moment's pool to `POOL` written lines that pass `check`, one call to the write role per moment that
    needs more. A moment the model answers badly keeps what passed and is asked again next time."""
    out = Wrote()
    todo = list(moments() if keys is None else keys)
    for i, key in enumerate(todo):
        if stop():
            out.left = todo[i:]
            break
        book = store.read()
        have = [w.text for w in book.lines.get(key, [])]
        if len(have) >= POOL:
            out.full.append(key)
            continue
        try:
            answer = ask(prompt_for(key, have, POOL - len(have) + 2), {"system": SYSTEM, "schema": SCHEMA})
            candidates = Answer.model_validate(answer.get("json")).lines
            model = str(answer.get("model") or "")
        except Exception as e:  # one moment failing (the service away, a refused call) must not lose the rest
            out.failed[key] = str(e) or type(e).__name__
            say(f"FAILED {key}: {out.failed[key]}")
            continue
        kept: list[int] = []
        store.edit(partial(_keep, key=key, candidates=candidates, model=model, out=out, kept=kept))
        added = kept[0]
        out.added[key] = added
        say(f"wrote {added:2}  {key}")
    return out


def _keep(b: Book, *, key: str, candidates: list[str], model: str, out: Wrote, kept: list[int]) -> None:
    """Add the candidates that pass `check` and are new to the pool, up to `POOL` (under the store's lock)."""
    pool = b.lines.setdefault(key, [])
    seen = {_norm(w.text) for w in pool} | {_norm(moments()[key].fixed)} | {_norm(x) for x in b.struck}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    added = 0
    for c in candidates:
        why = check(key, c)
        if why is None and _norm(c) in seen:
            why = "said already"
        if why is not None:
            out.refused.setdefault(key, []).append(f"{c}: {why}")
            continue
        if len(pool) >= POOL:
            break
        pool.append(Written(text=c, model=model, made=now))
        seen.add(_norm(c))
        added += 1
    kept.append(added)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z{}]+", " ", text.lower()).strip()


# ---- saying ---------------------------------------------------------------------------------------------------------

_SPEAKABLE = re.compile(r"^[A-Za-z][A-Za-z '’-]{0,23}$")


def speakable(nickname: str | None) -> str | None:
    """The nickname as said in a line, or None for one a line would not say well (an emoji, a number, a long one):
    then only the lines without a name are said."""
    if nickname is None:
        return None
    n = " ".join(nickname.split())
    return n if _SPEAKABLE.match(n) else None


class TalkOut(ApiModel):
    lines: dict[str, list[str]]  # moment -> what may be said there, the fixed line first (none for an intro)


def pools(book: Book, nickname: str | None) -> TalkOut:
    """What may be said at each moment for a learner called `nickname` (None: no name lines)."""
    name = speakable(nickname)
    out: dict[str, list[str]] = {}
    for key, m in moments().items():
        said = [m.fixed] if m.fixed else []
        for w in book.lines.get(key, []):
            if NAME in w.text and name is None:
                continue
            said.append(w.text.replace(NAME, name or ""))
        out[key] = said
    return TalkOut(lines=out)


def said(book: Book, nicknames: Iterable[str | None]) -> list[str]:
    """Every line the pools say, for these learners and for no learner: what the voice build makes clips of."""
    seen: dict[str, None] = {}
    for nick in [None, *nicknames]:
        for pool in pools(book, nick).lines.values():
            for line in pool:
                seen.setdefault(line, None)
    return list(seen)
