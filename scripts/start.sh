#!/usr/bin/env bash
# BASPAR CMMS — start script (development / single-server production).
# Production: run behind a reverse proxy (nginx/traefik) with TLS.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then PYTHON="python3"; fi

echo "[start] applying database migrations…"
"$PYTHON" scripts/migrate.py
echo "[start] seeding base data (idempotent)…"
"$PYTHON" scripts/seed.py

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
echo "[start] launching API + frontend on http://${HOST}:${PORT}"
exec "$PYTHON" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
