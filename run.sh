#!/usr/bin/env bash
# Loads .env (ANTHROPIC_API_KEY etc.) and runs the project in its venv.
# Usage: ./run.sh            -> dry run (main.py)
#        ./run.sh other.py   -> run a different entrypoint
set -euo pipefail
cd "$(dirname "$0")"
set -a
[ -f .env ] && . ./.env
set +a
exec ./.venv/bin/python "${1:-main.py}"
