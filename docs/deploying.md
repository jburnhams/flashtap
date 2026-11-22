# Deploying

The app is one process: `uv run flashtap serve` (FastAPI plus the built React app). Run it however you run long-lived services; [deploy/flashtap.service](../deploy/flashtap.service) is a systemd user-unit example.

1. Build the web app once per checkout: `cd web && npm ci && npm run build` (writes into `src/flashtap/server/static/`).
2. `uv sync --locked --no-dev` installs the runtime dependencies only.
3. Settings live in `~/.flashtap/settings.json` of the user the service runs as; `FLASHTAP_HOME` moves the folder. Nothing else is stored yet (no learner data until PR 4 of the plan, which brings a database).
4. Start `uv run --locked --no-dev flashtap serve --host 127.0.0.1 --port <port>` (default 8361). In a service, give uv's full path: systemd does not search `~/.local/bin`.
5. Put a reverse proxy in front if you want TLS or a shared hostname. The app works under a path prefix (`/<prefix>/`) with no configuration: see "Reverse-proxy support" in [AGENTS.md](../AGENTS.md). Forward the prefix-stripped path to the app.
6. Check `GET /api/health`: it returns `{"ok": true, "version": ..., "commit": ...}`.

## Keep the service and the repo in step

- Start the app only through the `flashtap` console script (`uv run flashtap serve`), never through a path to a source file.
- Change the unit in the same change as any rename of the package, the command or the port.
- After a restart, a port that answers is not proof the right app is running: compare `/api/health`'s `version` and `commit` with the checkout.
