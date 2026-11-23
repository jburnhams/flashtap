"""The recorded voice (flashtap.voice): how sentences are cut into lines, which lines Flashtap says, the clip store and
`build` with strata-models' speak call passed in (the true external edge; tests/integration runs it through the
`fake_models` service over HTTP)."""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from strata_python.testing import sine_wav
from strata_python.wav import WavError

from flashtap import rounds, voice
from flashtap.kinds import choose
from flashtap.mechanics import Mode

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "web/tests/fixtures/voice-segments.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize(("text", "want"), CASES)
def test_segments_agree_with_the_web_apps_fixture(text: str, want: list[str]):
    assert voice.segments(text) == want


def test_a_sound_line_is_its_ipa_between_slashes():
    assert voice.phoneme_of("/ʃ/") == "ʃ"
    assert voice.phoneme_of("Listen.") is None
    assert voice.is_vowel("iː")
    assert voice.is_vowel("aɪ")
    assert not voice.is_vowel("ʃ")
    assert not voice.is_vowel("j")


def test_the_browser_describes_a_sound_by_where_it_is_heard_never_by_its_letters():
    assert voice.describe("ʃ") == "the first sound in ship"
    assert voice.describe("ŋ") == "the last sound in ring"
    assert voice.describe("eɪ") == "the sound in rain"
    assert voice.describe("nope") == "a sound"
    assert voice.describe("ks") == "the last two sounds in fox"  # not "the last sound", which is /s/ alone
    assert voice.describe("kw") == "the first two sounds in quiz"
    assert voice.describe("tʃ") == "the first sound in chip"


def test_lines_hold_every_sound_once_after_the_sentences():
    said = voice.lines()
    sounds = [x for x in said if voice.phoneme_of(x)]
    assert said[-len(sounds) :] == sounds
    assert len(sounds) == len(set(sounds)) == 45
    assert {"Listen.", "Which letters make that sound?", "Try again.", "Counting or Listen?"} <= set(said)
    assert "/ʃ/" in said
    assert "0" in said
    assert "10" in said
    assert not any(", " in x and " and " in x and x[0].isdigit() for x in said)  # lists are their numbers


def test_rounds_beyond_the_sweep_say_nothing_new():
    """The sweep is exhaustive in practice: seeds it never saw add no line, so no line is left to the browser."""
    assert voice.sweep(range(10**6, 10**6 + 150)) <= set(voice.lines())


def test_the_app_lines_are_the_web_apps_own_wording():
    web = (ROOT / "web/src/play.ts").read_text(encoding="utf-8") + (ROOT / "web/src/screens/PlayScreen.tsx").read_text(
        encoding="utf-8"
    )
    for line in voice.APP_LINES:
        assert line in web, f"{line!r} is no longer said by the web app: update voice.APP_LINES"
    assert "The right one was" in web
    assert "You put" in web


def test_a_sounds_round_says_the_sound_and_never_its_letters():
    for seed in range(200):
        r = rounds.generate(Mode.SOUNDS, 6, seed)
        right = next(o for o in r.options if o.correct)
        token = next(x for x in voice.segments(r.say) if voice.phoneme_of(x))
        ph = voice.phoneme_of(token)
        spoken = " ".join(x for x in voice.segments(r.say) if not voice.phoneme_of(x)) + " " + r.prompt + " " + r.show
        assert right.word not in re.findall(r"[a-z]+", spoken.lower())  # the letters are never said or shown
        same = {g.grapheme for g in voice.lexicon.words().gpcs if g.phoneme == ph}
        assert right.word in same
        assert not any(o.word in same for o in r.options if not o.correct)
        assert token == choose.sound_token(str(ph))


# ---- the store ------------------------------------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> voice.Store:
    return voice.Store(tmp_path / "voice")


def test_store_keeps_a_clip_by_its_content_and_replaces_a_line(store: voice.Store):
    a, b = sine_wav(0.5, rate=24000), sine_wav(0.7, rate=24000, hz=330)
    c = store.put("Find the cow.", a, source="generated", voice="bf_emma", model="kokoro-v1", settings_hash="abc")
    assert c.file.startswith("clips/")
    assert (store.root / c.file).read_bytes() == a
    assert c.seconds == 0.5
    assert store.path_of(Path(c.file).name) == store.root / c.file
    assert store.path_of("../manifest.json") is None
    assert store.path_of("nope.wav") is None
    store.put("Find the cow.", b, source="generated", voice="bf_emma")
    assert store.read().clips["Find the cow."].seconds == 0.7
    assert store.remove("Find the cow.")
    assert not store.remove("Find the cow.")
    assert store.read().clips == {}


def test_store_refuses_what_is_not_a_short_pcm_wav(store: voice.Store):
    with pytest.raises(WavError):
        store.put("/m/", b"RIFF....not a wav", source="recorded", voice="recording")
    with pytest.raises(WavError):
        store.put("/m/", sine_wav(12.0, rate=24000), source="recorded", voice="recording")
    assert store.read().clips == {}


# ---- build ----------------------------------------------------------------------------------------------------------


class Speaker:
    """strata-models' speak as `build` calls it: writes a real WAV where the service would, records the params."""

    def __init__(self, tmp: Path, fail: str = "") -> None:
        self.tmp, self.fail, self.calls = tmp, fail, list[dict[str, Any]]()

    def __call__(self, text: str, **params: Any) -> tuple[dict[str, Any], Any]:
        self.calls.append({"text": text, **params})
        if text == self.fail:
            raise RuntimeError("the job failed")
        path = self.tmp / f"tts-{len(self.calls)}.wav"
        path.write_bytes(sine_wav(0.4, rate=24000, hz=200 + len(self.calls)))
        return {"path": str(path), "voice": params["voice"]}, SimpleNamespace(model="kokoro-v1", settings_hash="h1")


def test_build_makes_sentences_and_vowels_and_lists_consonants_to_record(store: voice.Store, tmp_path: Path):
    speak = Speaker(tmp_path)
    r = voice.build(store, ["Listen.", "/iː/", "/ʃ/"], speak=speak)
    assert r.made == ["Listen.", "/iː/"]
    assert r.to_record == ["/ʃ/"]
    assert not r.failed
    assert speak.calls[0] == {"text": "Listen.", "voice": "bf_emma", "language": "en-gb", "seed": 0}
    assert speak.calls[1]["phonemes"] == "iː"
    clip = store.read().clips["Listen."]
    assert (clip.source, clip.voice, clip.model, clip.settings_hash) == ("generated", "bf_emma", "kokoro-v1", "h1")


def test_build_keeps_what_it_has_remakes_another_voice_and_never_a_recording(store: voice.Store, tmp_path: Path):
    store.put("/ʃ/", sine_wav(0.6, rate=24000), source="recorded", voice="recording")
    voice.build(store, ["Listen."], speak=Speaker(tmp_path))
    speak = Speaker(tmp_path)
    assert voice.build(store, ["Listen.", "/ʃ/"], speak=speak).kept == ["Listen.", "/ʃ/"]
    assert speak.calls == []
    r = voice.build(store, ["Listen.", "/ʃ/"], voice="bm_lewis", model="kokoro-v1", speak=speak)
    assert r.made == ["Listen."]
    assert r.kept == ["/ʃ/"]
    assert speak.calls[0]["model"] == "kokoro-v1"
    assert voice.build(store, ["Listen."], voice="bm_lewis", force=True, speak=speak).made == ["Listen."]
    assert store.read().clips["/ʃ/"].source == "recorded"


def test_a_recording_kept_while_build_runs_is_not_undone(store: voice.Store, tmp_path: Path):
    """The build read the clips before the recording was kept; the store checks again under its lock."""
    speaker = Speaker(tmp_path)

    def speak_while_someone_records(text: str, **params: Any) -> tuple[dict[str, Any], Any]:
        store.put(text, sine_wav(0.6, rate=24000), source="recorded", voice="recording")
        return speaker(text, **params)

    said: list[str] = []
    r = voice.build(store, ["/iː/"], speak=speak_while_someone_records, say=said.append)
    assert r.kept == ["/iː/"]
    assert r.made == []
    assert store.read().clips["/iː/"].source == "recorded"
    assert said == ["kept  /iː/ (recorded meanwhile)"]


def test_one_failed_line_does_not_stop_the_rest(store: voice.Store, tmp_path: Path):
    said: list[str] = []
    r = voice.build(store, ["Listen.", "Try again."], speak=Speaker(tmp_path, fail="Listen."), say=said.append)
    assert r.failed == {"Listen.": "the job failed"}
    assert r.made == ["Try again."]
    assert said == ["FAILED Listen.: the job failed", "made  Try again."]


def test_voice_out_lists_every_sound_with_its_letters_and_clip(store: voice.Store):
    store.put("/k/", sine_wav(0.3, rate=24000), source="recorded", voice="recording")
    out = voice.voice_out(store)
    k = next(s for s in out.sounds if s.line == "/k/")
    assert k.graphemes == ["c", "k", "ck"]
    assert k.source == "recorded"
    assert k.clip == out.clips["/k/"]
    assert k.clip.startswith("api/v1/voice/clips/")
    assert not k.vowel
    sh = next(s for s in out.sounds if s.line == "/ʃ/")
    assert sh.clip is None
    assert sh.describe == "the first sound in ship"
