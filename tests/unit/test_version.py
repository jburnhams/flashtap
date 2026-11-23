import importlib.metadata

import flashtap


def test_version_comes_from_the_installed_package_metadata():
    assert flashtap.__version__ == importlib.metadata.version("flashtap")
