#!/usr/bin/env bash
# Starts both the backend and frontend dev servers from a single terminal.
# Run from the repo root:
#   ./run_web.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "No .venv found -- run ./setup.sh first."
  exit 1
fi
source .venv/bin/activate

if ! grep -qE "^ANTHROPIC_API_KEY=.+" .env 2>/dev/null; then
  echo "ANTHROPIC_API_KEY isn't set in .env -- open .env and set it first."
  exit 1
fi

cleanup() {
  echo ""
  echo "Stopping backend..."
  # uvicorn --reload runs as a reloader process that spawns a separate child
  # server process -- killing just the PID from `&` only kills the reloader's
  # immediate shell, leaving the actual server orphaned. Killing by port
  # instead is robust to that, and to however many subprocess layers exist.
  lsof -ti:8000 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://localhost:8000 ..."
(cd src && uvicorn web.api:app --reload --port 8000) &

sleep 1

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies (first run only)..."
  (cd frontend && npm install)
fi

echo ""
echo "Starting frontend -- open the URL Vite prints below (usually http://localhost:5173)."
echo "Press Ctrl+C here to stop both servers."
echo ""
(cd frontend && npm run dev)
