"""Where the learner records live, and bringing that database up to date.

strata_python.db decides the URL (`STRATA_DB_URL`, then `FLASHTAP_DATABASE_URL`, then the app's schema in the shared
Postgres named by `STRATA_DB_DATABASE`; a real Postgres also needs `STRATA_DB_LIVE=1`). When none of those is set,
the records go in a SQLite file beside the settings (`~/.flashtap/learners.db`, moved with `FLASHTAP_HOME`), so a
checkout plays and records with no database set up, and a deployment that has not been given one yet keeps working.
Either way the migrations run at first use, which is safe on every start (`Project.upgrade`).
"""

import os
from pathlib import Path

from sqlalchemy.engine import Engine
from strata_python.db import DatabaseNotConfigured, Project, connect, url_for

from flashtap import settings

APP = "flashtap"
# Built here rather than read from pyproject.toml, which an installed wheel does not have; tests/unit/test_database.py
# checks the two agree.
PROJECT = Project(
    root=Path(__file__).resolve().parents[1],
    app=APP,
    models="flashtap.learners.models:Base",
    migrations_dir=Path(__file__).resolve().parents[1] / "migrations",
)


def sqlite_path() -> str:
    return os.path.join(settings.SETTINGS.home(), "learners.db")


def url() -> str:
    """The configured database, or the SQLite file beside the settings when none is."""
    try:
        return url_for(APP)
    except DatabaseNotConfigured:
        return "sqlite:///" + sqlite_path()


def open_engine(where: str | None = None) -> Engine:
    """An engine on `where` (default `url()`), migrated to the newest revision."""
    where = where or url()
    if where.startswith("sqlite:///"):
        os.makedirs(os.path.dirname(where.removeprefix("sqlite:///")) or ".", exist_ok=True)
    engine = connect(where)
    PROJECT.upgrade(engine)
    return engine
