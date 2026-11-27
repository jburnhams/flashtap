import os

import pytest

from flashtap import settings
from flashtap.rounds import Mode


def test_defaults_and_env_overrides(monkeypatch):
    assert settings.SETTINGS.home() == os.environ["FLASHTAP_HOME"]  # the plugin's isolated folder
    assert settings.mode() is Mode.MIXED
    assert settings.choices() == 4
    assert settings.tries() == 0
    monkeypatch.setenv("FLASHTAP_MODE", " Counting ")
    monkeypatch.setenv("FLASHTAP_CHOICES", "6")
    assert settings.mode() is Mode.COUNTING
    assert settings.choices() == 6


def test_save_validates_each_setting():
    assert settings.SETTINGS.save({"mode": "letters", "choices": "3", "tries": "2"}) == {
        "mode": "letters",
        "choices": "3",
        "tries": "2",
    }
    assert settings.mode() is Mode.LETTERS
    with pytest.raises(ValueError, match="mode: must be one of"):
        settings.SETTINGS.save({"mode": "spelling"})
    with pytest.raises(ValueError, match="from 2 to 8"):
        settings.SETTINGS.save({"choices": "9"})
    with pytest.raises(ValueError, match="from 0 to 7"):
        settings.SETTINGS.save({"tries": "8"})
    assert settings.choices() == 3  # a refused save changes nothing


def test_next_after_counts_down_three_seconds_by_default_and_can_wait_for_a_tap():
    assert settings.next_after() == 3
    settings.SETTINGS.save({"next_after": "0"})
    assert settings.next_after() == 0
    with pytest.raises(ValueError, match="from 0 to 10"):
        settings.SETTINGS.save({"next_after": "11"})


def test_session_settings_have_defaults_ranges_and_an_off_switch(monkeypatch):
    got = (
        settings.session_rounds(),
        settings.session_minutes(),
        settings.break_every(),
        settings.choice_every(),
        settings.rate_every(),
    )
    assert got == (20, 15, 10, 5, 4)
    settings.SETTINGS.save({"break_every": "0", "choice_every": "0", "rate_every": "0", "session_rounds": "100"})
    assert (settings.break_every(), settings.choice_every(), settings.rate_every(), settings.session_rounds()) == (
        0,
        0,
        0,
        100,
    )
    with pytest.raises(ValueError, match="from 1 to 100"):
        settings.SETTINGS.save({"session_rounds": "0"})
    with pytest.raises(ValueError, match="from 1 to 120"):
        settings.SETTINGS.save({"session_minutes": "121"})
    monkeypatch.setenv("FLASHTAP_SESSION_MINUTES", "30")
    assert settings.session_minutes() == 30
