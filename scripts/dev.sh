#!/usr/bin/env bash
# Boot the Argus backend and frontend together for local development.
#
#   ./scripts/dev.sh
#
# Backend  -> http://localhost:8000  (FastAPI, reload)
# Frontend -> http://localhost:3000  (Next.js dev)
#
# Ctrl-C stops both.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  # Kill the whole process group so child servers stop too.
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on :8000 ..."
(
  cd "$ROOT_DIR/backend"
  uv run uvicorn app.main:app --reload --port 8000
) &

echo "Starting frontend on :3000 ..."
(
  cd "$ROOT_DIR/frontend"
  pnpm dev --port 3000
) &

wait
