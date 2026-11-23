"""strata_python.db's standard checks: the migrated schema matches the models, and every migration goes up, down and
up again (on SQLite; `pytest --pg` on a throwaway Postgres)."""

from strata_python.db.testing import test_migrations, test_schema_matches_models

__all__ = ["test_migrations", "test_schema_matches_models"]
