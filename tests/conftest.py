"""Shared pytest configuration. Hermetic tests (own home and data folder, no network, no stray override variables), the `integration` marker on tests/integration and the
`http_server` / `live_app` / `fake_*` fixtures all come from the strata-python plugin, configured in pyproject.toml. Add a fixture here only when both suites need it."""

import pytest


@pytest.fixture(autouse=True)
def _learner_records(db_env: str) -> str:
    """Every test's app records into its own fresh, migrated database (strata_python.db's `db_env`: SQLite copied from
    a template migrated once per run; `pytest --pg` for a throwaway Postgres), never the owner's."""
    return db_env
