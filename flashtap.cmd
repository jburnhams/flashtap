@echo off
rem Launcher for Windows: runs the flashtap CLI in the uv-managed project environment (same as `uv run flashtap`).
uv run --project "%~dp0." flashtap %*
