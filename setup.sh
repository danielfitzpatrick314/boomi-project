#!/usr/bin/env bash
# One-command setup: venv, deps, .env template. Run from the repo root:
#   ./setup.sh
set -e

python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "Created .env from .env.example."
fi

if ! grep -qE "^ANTHROPIC_API_KEY=.+" .env; then
  echo ""
  echo "=============================================================="
  echo "  ACTION NEEDED: open .env and set ANTHROPIC_API_KEY to your"
  echo "  real key before running anything else. Nothing works without"
  echo "  it -- this is not optional."
  echo "=============================================================="
else
  echo ""
  echo "Setup complete. .env already has a key set."
fi

echo ""
echo "This script's venv activation does not carry over to your shell -- run this"
echo "yourself now (and in any new terminal), then the CLI commands below it:"
echo ""
echo "  source .venv/bin/activate"
echo "  python scripts/run_investigation.py --recall-number D-1178-2018"
