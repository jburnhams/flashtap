"""Where the learner records live.

strata_python.db decides the URL (`STRATA_DB_URL`, then `FLASHTAP_DATABASE_URL`, then the app's schema in the shared
Postgres named by `STRATA_DB_DATABASE`; a real Postgres also needs `STRATA_DB_LIVE=1`). When none of those is set,
the records go in a SQLite file beside the settings (`~/.flashtap/learners.db`, moved with `FLASHTAP_HOME`), so a
checkout plays and records with no database set up, and a deployment that has not been given one yet keeps working.
Either way the migrations run when the database is opened (`Project.open`), which is safe on every start. The server
opens it on the first request that needs it (`strata_python.db.web.add_database` in `server/app.py`).
"""

from sqlalchemy.engine import Engine
from strata_python.db import Project, local_url

from flashtap import settings

# src/flashtap/strata-db.toml, found from here in a checkout and in an installed wheel alike.
PROJECT = Project.load(__file__)


def default_url() -> str:
    """The SQLite file used when no database is configured. Named `learners.db`, as it was before strata_python had
    `local_url`, so a checkout's existing records are still found."""
    return local_url(settings.SETTINGS, "learners")


def open_engine(where: str | None = None) -> Engine:
    """An engine on `where` (default: the configured database, else `default_url()`), migrated to the newest revision."""
    return PROJECT.open(where, default=default_url())
