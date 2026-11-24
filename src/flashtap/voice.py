"""Voice clips: every line Flashtap says, recorded once in one UK voice, with the browser's voice as the fallback.

Browser voices differ by device, some read "Find the" in an American accent, and none can say a phonics sound alone
(/ʃ/ comes out as "es aitch" or nothing). So each line a round can say is made once by strata-models' `speak` role
(`flashtap voice build`, through `strata_python.clients.models`) and kept with its provenance; the web app plays the
clips (strata-react's `speak(parts)`) and the browser says only what has no clip.

- **Lines** are sentences and sounds. `say` text is split by `segments`: a sound on its own is written `/IPA/`
  (`kinds.choose.sound_token`), everything else is cut into sentences, and a list of numbers ("0, 1, 8 and 10.") into
  its numbers, since every list would be a line of its own. The web app splits the same way (`web/src/voice.ts`;
  both are tested against `web/tests/fixtures/voice-segments.json`), so a clip is found by the sentence's own text.
- **Which lines** (`lines()`): what every template says and answers over a sweep of seeds, choices and steps of difficulty, the sentences the
  web app builds around them (`web/src/play.ts`, `PlayScreen.tsx`; kept in step by hand, see `APP_LINES`), and each
  sound of the phonics inventory. tests/unit/test_voice.py checks that rounds from seeds outside the sweep say nothing
  new, so a line is never silently left to the browser.
- **Sounds**: a vowel sound is made from its IPA (`phonemes`, strata-models PR #110). A consonant is not: Kokoro wraps a
  lone /ʃ/ or /m/ in a vowel ("uh-sh-uh"), which is the mistake phonics teaching works to undo, so consonants are
  recorded by a person in the app (the Sounds screen, `PUT /api/v1/voice/recordings`) and `build` never makes them
  (strata-models issue #111 would let it). Until one is recorded the browser says a description ("the first sound in
  ship"), never the letters, which would give the answer.
- **The store** is a folder beside the settings (`~/.flashtap/voice/`, moved with `FLASHTAP_HOME`): `manifest.json`
  (line -> file, source, voice, model, settings hash) and `clips/<sha256 of the file>.wav`, named by content so the
  browser may cache a clip forever. A recording is never replaced by `build`. Nothing here is in git: a recording is
  a person's voice (AGENTS.md rule 8).
"""

import hashlib
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from strata_python import oslib
from strata_python.contracts import ApiModel
from strata_python.wav import read_wav

from flashtap import lexicon, rounds, settings
from flashtap.mechanics import Mechanic

APP = "flashtap"  # the app name strata-models files the jobs under
DEFAULT_VOICE = "bf_emma"  # Kokoro's UK English voices start b (bf_ female, bm_ male); a clear, unhurried one
LANGUAGE = "en-gb"
MAX_RECORDING_S = 10.0
MAX_RECORDING_BYTES = 4_000_000

Source = Literal["generated", "recorded"]

_SOUND = re.compile(r"(/[^/\s]+/)")
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
_EDGE = re.compile(r"^[\s.,;:!?]+|\s+$")
_NUMBER_LIST = re.compile(r"^\d+(?:, \d+)* and \d+[.?!]$")  # "0, 1, 8 and 10." (Order's answer)
# IPA vowel letters of the inventory (traditional British transcription): a sound with one is said from its IPA.
_VOWEL_LETTERS = set("aeiouæɪɒʌʊəɜɑɔ")


def segments(text: str) -> list[str]:
    """The lines of a sentence or prompt, in order: each `/IPA/` sound on its own, the rest cut into sentences."""
    out: list[str] = []
    for piece in _SOUND.split(text):
        if _SOUND.fullmatch(piece):
            out.append(piece)
            continue
        for sentence in _SENTENCE_END.split(piece):
            s = " ".join(sentence.split())
            if not _EDGE.sub("", s):  # a lone "." left between two sounds is not a line
                continue
            s = s.lstrip(" .,;:")
            if _NUMBER_LIST.match(s):  # a list of numbers is its numbers, one clip each: 11 lines, not every list
                out.extend(re.findall(r"\d+", s))
            else:
                out.append(s)
    return out


def phoneme_of(line: str) -> str | None:
    """The IPA of a sound line (`/ʃ/` -> `ʃ`), None for a sentence."""
    return line[1:-1] if _SOUND.fullmatch(line) else None


def is_vowel(phoneme: str) -> bool:
    return any(c in _VOWEL_LETTERS for c in phoneme)


_CLUSTERS = frozenset({"ks", "kw"})  # one grapheme, two consonant sounds (tʃ and dʒ are one sound each)


def describe(phoneme: str) -> str:
    """What the browser says for a sound with no clip: where it is heard in an example word ("the first sound in
    ship"). Never the letters, which are the answer, and never the sound itself, which a browser voice cannot say."""
    gpcs = [g for g in lexicon.words().gpcs if g.phoneme == phoneme and g.example]
    # x is /ks/ and qu /kw/: two sounds, so "the last sound in fox" would name /s/ alone, which an s tile also makes
    what = "two sounds" if phoneme in _CLUSTERS else "sound"
    for g in gpcs:
        if g.example.startswith(g.grapheme):
            return f"the first {what} in {g.example}"
    for g in gpcs:
        if g.example.endswith(g.grapheme):
            return f"the last {what} in {g.example}"
    return f"the sound in {gpcs[0].example}" if gpcs else "a sound"


# Sentences the web app says that no round carries, or builds from a round's own (web/src/play.ts feedback and
# placeFeedback, PlayScreen's pick, break and faces). Kept in step by hand: a sentence missing here is said by the
# browser, which still works, and tests/unit/test_voice.py pins these against play.ts's wording.
APP_LINES = (
    "Try again.",
    "Not yet.",
    "Here is the answer.",
    "That’s too many.",
    "That’s not enough.",
    "Which one next?",
    "How was that one?",
    "Time for a break?",
)

SWEEP_SEEDS = (
    1200  # seeds per template and number of choices: at 1,000 the rounds already said everything (test_voice.py)
)
# Seeds per step of difficulty. A step is one number of choices, not seven, and the higher steps pair every countable
# picture with every number to 10, so they need more seeds each to say everything (at 1,200, "Put 10 peppers" was missed).
STEP_SEEDS = 6000


def _round_lines(r: rounds.Round) -> Iterable[str]:
    yield from segments(r.say)
    for o in r.options:
        yield from segments(o.feedback)
    if r.options:  # a choose round missed: play.ts adds where the answer was
        right = next(o for o in r.options if o.correct)
        yield f"The right one was {right.word if right.word.isdigit() else f'the {right.word}'}."
    if r.done_feedback:
        yield from segments(r.done_feedback)
    if r.mechanic is Mechanic.GIVE_N:
        basket = r.places[0]
        for n in range(len(r.pieces) + 1):
            yield f"You put {n} in {basket.word}."


def sweep(seeds: Iterable[int], step_seeds: Iterable[int] | None = None) -> set[str]:
    """Every line the rounds of these seeds say, over every template and number of choices, and every step of
    difficulty (the engine's steps reach numbers the rounds by hand never ask about: "Put 8 ducks in the basket.")."""
    seen: set[str] = set()
    every = list(seeds)
    stepped = every if step_seeds is None else list(step_seeds)
    for mode in rounds.PLAYABLE:
        for choices in range(rounds.MIN_CHOICES, rounds.MAX_CHOICES + 1):
            for seed in every:
                seen.update(_round_lines(rounds.generate(mode, choices, seed)))
        for level in range(len(rounds.TEMPLATES[mode].levels)):
            for seed in stepped:
                seen.update(_round_lines(rounds.at_level(mode, level, seed)))
    return seen


@cache
def lines() -> list[str]:
    """Every line Flashtap says, sentences first (sorted), then the phonics sounds in the inventory's order."""
    said = sweep(range(SWEEP_SEEDS), range(STEP_SEEDS)) | set(APP_LINES)
    titles = [rounds.TEMPLATES[m].name for m in rounds.PLAYABLE]
    said.update(f"{a} or {b}?" for a in titles for b in titles if a != b)  # a choice of two (PlayScreen PickOne)
    sounds: list[str] = []
    for g in lexicon.words().gpcs:
        token = f"/{g.phoneme}/"
        if token not in sounds:
            sounds.append(token)
    return sorted(s for s in said if phoneme_of(s) is None) + sounds


# ---- the store ------------------------------------------------------------------------------------------------------


class Clip(BaseModel):
    file: str  # clips/<sha256[:16]>.wav
    source: Source
    voice: str  # a Kokoro voice name, or "recording"
    model: str = ""  # the strata-models model that made it; empty for a recording
    settings_hash: str = ""  # the model's settings when it ran (strata-models #103): a change remakes the clip
    seconds: float
    made: str  # ISO date and time


class Manifest(BaseModel):
    version: int = 1
    clips: dict[str, Clip] = {}


def home() -> Path:
    return Path(settings.SETTINGS.home()) / "voice"


@dataclass
class Store:
    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def read(self) -> Manifest:
        try:
            return Manifest.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Manifest()

    def clip(self, line: str) -> Clip | None:
        return self.read().clips.get(line)

    def path_of(self, name: str) -> Path | None:
        """The file of a clip by its served name (`<hash>.wav`), or None for any name the manifest does not hold."""
        files = {Path(c.file).name: c.file for c in self.read().clips.values()}
        return self.root / files[name] if name in files else None

    def _edit(self, change: Callable[[Manifest], None]) -> None:
        """Read, change and write the manifest under a lock: `build` and a recording from the app can overlap."""
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a+") as lock, oslib.file_lock(lock):
            m = self.read()
            change(m)
            fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(m.model_dump_json(indent=1))
            os.replace(tmp, self.manifest_path)

    def put(
        self, line: str, wav: bytes, *, source: Source, voice: str, model: str = "", settings_hash: str = ""
    ) -> Clip:
        """Keep `wav` as the clip of `line` (any earlier clip of it is replaced; its file stays if another line uses it)
        and return the clip the line now has. A made clip never replaces a recording: that is checked under the lock,
        so a recording kept while `build` runs is not undone by it, and the recording is returned."""
        info = read_wav(wav, max_seconds=MAX_RECORDING_S if source == "recorded" else None)
        name = f"clips/{hashlib.sha256(wav).hexdigest()[:16]}.wav"
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(wav)
            os.replace(tmp, target)
        clip = Clip(
            file=name,
            source=source,
            voice=voice,
            model=model,
            settings_hash=settings_hash,
            seconds=round(info.seconds, 3),
            made=datetime.now(UTC).isoformat(timespec="seconds"),
        )

        kept = clip

        def change(m: Manifest) -> None:
            nonlocal kept
            now = m.clips.get(line)
            if source == "generated" and now is not None and now.source == "recorded":
                kept = now
                return
            m.clips[line] = clip

        self._edit(change)
        return kept

    def remove(self, line: str) -> bool:
        removed = False

        def change(m: Manifest) -> None:
            nonlocal removed
            removed = m.clips.pop(line, None) is not None

        self._edit(change)
        return removed


# ---- making clips ---------------------------------------------------------------------------------------------------


class Built(BaseModel):
    made: list[str] = []
    kept: list[str] = []  # already there in this voice and settings (or recorded)
    to_record: list[str] = []  # consonant sounds: a person records them
    failed: dict[str, str] = {}


Speak = Callable[..., tuple[dict[str, Any], Any]]  # clients.models.run_with_provenance's shape


def _speak_default(text: str, **params: Any) -> tuple[dict[str, Any], Any]:
    from strata_python.clients import models

    return models.run_with_provenance("speak", {**params, "text": text}, APP)


def build(
    store: Store,
    wanted: Iterable[str],
    *,
    voice: str = DEFAULT_VOICE,
    model: str | None = None,
    force: bool = False,
    speak: Speak = _speak_default,
    say: Callable[[str], None] = lambda _: None,
) -> Built:
    """Make the missing clips of `wanted` with strata-models. A clip is remade when it is in another voice, from other
    model settings, or `force`; a recording never is. Consonant sounds are listed to record, not made."""
    out = Built()
    have = store.read().clips
    for line in wanted:
        old = have.get(line)
        if old is not None and old.source == "recorded":
            out.kept.append(line)
            continue
        ph = phoneme_of(line)
        if ph is not None and not is_vowel(ph):
            out.to_record.append(line)
            continue
        if old is not None and old.voice == voice and not force:
            out.kept.append(line)
            continue
        params: dict[str, Any] = {"voice": voice, "language": LANGUAGE, "seed": 0}
        if ph is not None:
            params["phonemes"] = ph
        if model:
            params["model"] = model
        try:
            result, prov = speak(line, **params)
            wav = Path(str(result["path"])).read_bytes()
            got = store.put(
                line,
                wav,
                source="generated",
                voice=str(result.get("voice") or voice),
                model=str(getattr(prov, "model", "") or ""),
                settings_hash=str(getattr(prov, "settings_hash", "") or ""),
            )
            if got.source == "recorded":  # recorded while this line was being made: the recording stands
                out.kept.append(line)
                say(f"kept  {line} (recorded meanwhile)")
                continue
            out.made.append(line)
            say(f"made  {line}")
        except Exception as e:  # one line failing (a refused param, a missing file) must not lose the rest
            out.failed[line] = str(e) or type(e).__name__
            say(f"FAILED {line}: {out.failed[line]}")
    return out


# ---- what the web app reads -----------------------------------------------------------------------------------------


class SoundRow(ApiModel):
    line: str  # "/ʃ/"
    phoneme: str
    graphemes: list[str]  # the letters that write it in the inventory: sh; c, k, ck
    example: str  # a word that shows it
    describe: str  # what the browser says until it has a clip
    vowel: bool  # made from IPA by `build`; a consonant is recorded by a person
    clip: str | None  # the clip's URL (relative: the web app puts it through withBase), None for none
    source: Source | None


class VoiceOut(ApiModel):
    clips: dict[str, str]  # line -> clip URL, for every line that has one
    sounds: list[SoundRow]  # every phonics sound, recorded or not, in the inventory's order


def clip_url(c: Clip) -> str:
    return f"api/v1/voice/clips/{Path(c.file).name}"


def sound_rows(m: Manifest) -> list[SoundRow]:
    rows: dict[str, SoundRow] = {}
    for g in lexicon.words().gpcs:
        line = f"/{g.phoneme}/"
        if line in rows:
            if g.grapheme not in rows[line].graphemes:
                rows[line].graphemes.append(g.grapheme)
            continue
        c = m.clips.get(line)
        rows[line] = SoundRow(
            line=line,
            phoneme=g.phoneme,
            graphemes=[g.grapheme],
            example=g.example,
            describe=describe(g.phoneme),
            vowel=is_vowel(g.phoneme),
            clip=clip_url(c) if c else None,
            source=c.source if c else None,
        )
    return list(rows.values())


def voice_out(store: Store) -> VoiceOut:
    m = store.read()
    return VoiceOut(clips={k: clip_url(c) for k, c in m.clips.items()}, sounds=sound_rows(m))
