"""flashtap: learning games that progress by ability, served as a FastAPI + strata-react web app."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("flashtap")  # pyproject.toml is the one place the version lives
except PackageNotFoundError:
    __version__ = "0+unknown"  # running from a source tree that was never installed
