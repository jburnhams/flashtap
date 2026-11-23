"""User settings: one JSON file, `~/.flashtap/settings.json` (the folder can be moved with the FLASHTAP_HOME environment variable).

  mode      which kind of round to play by default: matching, colours, shapes, letters, counting or mixed (default: mixed).
  choices   how many pictures or numbers a round offers, 2 to 8 (default: 4).
  tries     taps allowed before a round counts as missed, 0 for no limit (default: 0). Kept below the number of choices.

FLASHTAP_MODE, FLASHTAP_CHOICES and FLASHTAP_TRIES override the file. The file handling, precedence and validation are
[strata_python.settings](https://github.com/jburnhams/strata-python); this module only declares the app's settings."""

from strata_python.settings import Setting, Settings, whole_between

from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, Mode


def mode_name(value: str) -> str:
    v = value.strip().lower()
    if v not in set(Mode):
        raise ValueError(f"mode must be one of {', '.join(Mode)}, not {value!r}")
    return v


SETTINGS = Settings(
    "flashtap",
    [
        Setting("mode", default=Mode.MIXED.value, normalise=mode_name),
        Setting("choices", default="4", normalise=whole_between(MIN_CHOICES, MAX_CHOICES)),
        Setting("tries", default="0", normalise=whole_between(0, MAX_CHOICES - 1)),
    ],
)


def mode() -> Mode:
    return Mode(SETTINGS.get("mode"))


def choices() -> int:
    return SETTINGS.get_int("choices")


def tries() -> int:
    return SETTINGS.get_int("tries")
