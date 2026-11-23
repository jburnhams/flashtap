"""strata_python.db's standard checks: the migrated schema matches the models, and every migration goes up, down and
up again (on SQLite; `pytest --pg` on a throwaway Postgres)."""

import importlib
import json

from sqlalchemy import text
from strata_python.db.project import Project
from strata_python.db.scratch import scratch_database
from strata_python.db.testing import scratch_engine, test_migrations, test_schema_matches_models

from flashtap import rounds

__all__ = ["test_migrations", "test_schema_matches_models"]

# A revision's file name starts with a date, so it is loaded by name rather than imported.
CONTENT: dict[str, dict[str, int]] = importlib.import_module(
    "flashtap.migrations.20261123_ad08d3806978_content_pack_versions_on_attempts_and_"
).CONTENT


def test_content_migration_fills_the_packs_each_old_round_drew_from(db_backend: str, db_project: Project) -> None:
    """Rows logged before attempts recorded their packs get the packs their kind drew from, all at version 1, the only
    version any pack had; a decision without a round keeps none."""
    with scratch_database(db_backend == "postgres") as url:
        eng = scratch_engine(url)
        try:
            db_project.upgrade(eng, "8611114c2acc")
            at = "2026-11-01 00:00:00+00:00"  # text, which both databases read as a time
            with eng.begin() as c:
                c.execute(text("INSERT INTO learners (id, nickname, created_at) VALUES ('a1', 'Fox', :at)"), {"at": at})
                c.execute(
                    text("INSERT INTO sessions (id, learner_id, started_at, last_at) VALUES ('s1', 'a1', :at, :at)"),
                    {"at": at},
                )
                c.execute(
                    text(
                        "INSERT INTO attempts (event_id, learner_id, session_id, mode, version, choices, seed, mechanic,"
                        " options, skills, asked, presented_at, answered_at, first_answer, first_correct, tries,"
                        " outcome, received_at) VALUES ('e1', 'a1', 's1', 'counting', 1, 3, 7, 'select_one', 3, '[]',"
                        " 'counting', :at, :at, '{}', true, 1, 'right', :at)"
                    ),
                    {"at": at},
                )
                for i, (action, mode) in enumerate([("round", "listen"), ("break", None)]):
                    c.execute(
                        text(
                            "INSERT INTO decisions (id, learner_id, session_id, seq, at, policy, action, mode, rationale,"
                            " probability, candidates) VALUES (:id, 'a1', 's1', :seq, :at, 'p@1', :action, :mode, '[]',"
                            " 1, '[]')"
                        ),
                        {"id": f"d{i}", "seq": i, "at": at, "action": action, "mode": mode},
                    )
            db_project.upgrade(eng)
            with eng.connect() as c:
                attempt = c.execute(text("SELECT content FROM attempts")).scalar_one()
                decided = {r.id: r.content for r in c.execute(text("SELECT id, content FROM decisions"))}
        finally:
            eng.dispose()

    def read(v: object) -> object:
        return json.loads(v) if isinstance(v, str) else v  # SQLite hands back the JSON text, Postgres the value

    assert read(attempt) == CONTENT["counting"]
    assert read(decided["d0"]) == CONTENT["listen"]
    assert read(decided["d1"]) is None
    # The table names the packs each kind draws from today. A pack's version raised later does not touch it (old rows
    # were made at version 1); a kind that comes to draw from other packs changes this line, never the migration.
    # A kind added after the migration (Sounds) has no old rows to fill, so it is not in the table.
    older = {m.value: set(rounds.content_of(m)) for m in rounds.PLAYABLE if m.value in CONTENT}
    assert older == {k: set(v) for k, v in CONTENT.items()}
    assert len(older) == len(CONTENT)
    assert {v for c in CONTENT.values() for v in c.values()} == {1}
