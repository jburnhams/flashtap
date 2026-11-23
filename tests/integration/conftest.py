"""Integration-suite fixtures: the CLI (in-process and as a real process) and the HTTP API over real on-disk settings."""

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from strata_python.db.web import database
from strata_python.testing import CliResult, run_cli, run_module

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))


@pytest.fixture
def cli() -> Callable[..., CliResult]:
    """`cli('round', '--seed', 1)` -> CliResult(stdout, stderr, code), in this process."""
    from flashtap import cli as C

    return lambda *args, check=True: run_cli(C.main, *args, check=check)


@pytest.fixture
def cli_subprocess() -> Callable[..., CliResult]:
    """The same through a real `python -m flashtap` process: the entry-point smoke test."""
    return lambda *args, check=True: run_module("flashtap", *args, src=SRC, check=check)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """The HTTP API over the real settings file and a fresh learner database (tests/conftest.py)."""
    from flashtap.server.app import create_app

    app = create_app()
    yield TestClient(app)
    database(app).close()  # the learner database, if a learner route opened it
