"""Shared pytest configuration. Hermetic tests (own home and data folder, no network, no stray override variables), the `integration` marker on tests/integration and the
`http_server` / `live_app` / `fake_*` fixtures all come from the strata-python plugin, configured in pyproject.toml. Add a fixture here only when both suites need it."""
