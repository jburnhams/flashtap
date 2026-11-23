# Deploying

The app is one process: `uv run flashtap serve` (FastAPI plus the built React app). Run it however you run long-lived services; [deploy/flashtap.service](../deploy/flashtap.service) is a systemd user-unit example.

1. Build the web app once per checkout: `cd web && npm ci && npm run build` (writes into `src/flashtap/server/static/`).
2. `uv sync --locked --no-dev` installs the runtime dependencies only.
3. Settings live in `~/.flashtap/settings.json` of the user the service runs as; `FLASHTAP_HOME` moves the folder.
4. Learner records go where [strata_python.db](https://github.com/jburnhams/strata-python) points: `STRATA_DB_URL` or `FLASHTAP_DATABASE_URL` if set, else the `flashtap` schema of the shared Postgres named by `STRATA_DB_DATABASE` (which also needs `STRATA_DB_LIVE=1` in the service's environment, and the schema and role made once with `uv run strata-db new-app flashtap`). With none of those set they go in a SQLite file beside the settings (`~/.flashtap/learners.db`), so a fresh install records with nothing to set up. The migrations run on the first request that needs the records. The records identify learners only by nickname, but they are about children: keep them off public hosts and behind a login, and out of any repository. Moving from the SQLite file to Postgres does not copy the records: export each learner first if they matter.
5. Start `uv run --locked --no-dev flashtap serve --host 127.0.0.1 --port <port>` (default 8361). In a service, give uv's full path: systemd does not search `~/.local/bin`.
6. Put a reverse proxy in front if you want TLS or a shared hostname. The app works under a path prefix (`/<prefix>/`) with no configuration: see "Reverse-proxy support" in [AGENTS.md](../AGENTS.md). Forward the prefix-stripped path to the app.
7. Check `GET /api/health`: it returns `{"ok": true, "version": ..., "commit": ...}`.

## Keep the service and the repo in step

- Start the app only through the `flashtap` console script (`uv run flashtap serve`), never through a path to a source file.
- Change the unit in the same change as any rename of the package, the command or the port.
- After a restart, a port that answers is not proof the right app is running: compare `/api/health`'s `version` and `commit` with the checkout.
