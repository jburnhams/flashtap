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
    with pytest.raises(ValueError, match="mode must be one of"):
        settings.SETTINGS.save({"mode": "spelling"})
    with pytest.raises(ValueError, match="from 2 to 8"):
        settings.SETTINGS.save({"choices": "9"})
    with pytest.raises(ValueError, match="from 0 to 7"):
        settings.SETTINGS.save({"tries": "8"})
    assert settings.choices() == 3  # a refused save changes nothing
