"""User settings: one JSON file, `~/.flashtap/settings.json` (the folder can be moved with the FLASHTAP_HOME environment variable).

  mode      which kind of round to play by default: matching, colours, shapes, letters, counting or mixed (default: mixed).
  choices   how many pictures or numbers a round offers, 2 to 8 (default: 4). For rounds the grown-up picks: the engine
            ("Chosen for them") sets each round's step of difficulty from the learner's answers (rounds.Level).
  tries     taps allowed before a round counts as missed, 0 for no limit (default: 0). Kept below the number of choices.
  next_after  seconds Next counts down once a round is over before the next round comes by itself, 0 to wait for a
            tap on Next (default: 3). With the three faces asked, it counts from a face tapped.

Sessions the adaptive engine plans ("Chosen for them" on Play; snapshotted into each session when it starts, so a
change applies from the next session and a replay uses what the session ran with):

  session_rounds   rounds in a session at most, 1 to 100 (default: 20).
  session_minutes  minutes in a session at most, 1 to 120 (default: 15).
  break_every      rounds between offered breaks, 0 for none (default: 10). A break after three misses running is
                   offered whatever this says: frustration is constrained, never traded (spec §12).
  choice_every     every this many rounds the learner picks between two activities, 0 for never (default: 5).
  rate_every       every this many rounds the learner is asked how it was (three faces, optional), 0 for never
                   (default: 4). Also used when the grown-up picks the kind of round.

FLASHTAP_<KEY> (FLASHTAP_MODE, FLASHTAP_SESSION_ROUNDS ...) overrides the file. The file handling, precedence and validation are
[strata_python.settings](https://github.com/jburnhams/strata-python); this module only declares the app's settings."""

from strata_python.settings import Setting, Settings, whole_between

from flashtap.rounds import MAX_CHOICES, MIN_CHOICES, Mode

SETTINGS = Settings(
    "flashtap",
    [
        # choices: matched without regard to case, refused with the list, and an enum in /api/openapi.json, so the web
        # app's generated type names the kinds. numbers: choices and tries are sent as JSON numbers with their limits.
        Setting("mode", default=Mode.MIXED.value, choices=[m.value for m in Mode]),
        Setting("choices", default="4", normalise=whole_between(MIN_CHOICES, MAX_CHOICES)),
        Setting("tries", default="0", normalise=whole_between(0, MAX_CHOICES - 1)),
        Setting("next_after", default="3", normalise=whole_between(0, 10)),
        Setting("session_rounds", default="20", normalise=whole_between(1, 100)),
        Setting("session_minutes", default="15", normalise=whole_between(1, 120)),
        Setting("break_every", default="10", normalise=whole_between(0, 100)),
        Setting("choice_every", default="5", normalise=whole_between(0, 20)),
        Setting("rate_every", default="4", normalise=whole_between(0, 20)),
    ],
    numbers=True,
)


def mode() -> Mode:
    return Mode(SETTINGS.get("mode"))


def choices() -> int:
    return SETTINGS.get_int("choices")


def tries() -> int:
    return SETTINGS.get_int("tries")


def next_after() -> int:
    return SETTINGS.get_int("next_after")


def session_rounds() -> int:
    return SETTINGS.get_int("session_rounds")


def session_minutes() -> int:
    return SETTINGS.get_int("session_minutes")


def break_every() -> int:
    return SETTINGS.get_int("break_every")


def choice_every() -> int:
    return SETTINGS.get_int("choice_every")


def rate_every() -> int:
    return SETTINGS.get_int("rate_every")
