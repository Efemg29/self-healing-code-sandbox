#!/usr/bin/env bash
# Boot-time start: FastAPI UI/API for the self-healing sandbox.
set -euo pipefail
cd /workspace

if [[ ! -d .venv ]]; then
  echo "Missing .venv; run scripts/install.sh first" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

export MOCK_LLM="${MOCK_LLM:-true}"
export ALLOW_LOCAL_SANDBOX="${ALLOW_LOCAL_SANDBOX:-true}"
export PYTHONPATH=/workspace
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-43127}"

exec python main.py serve --host "$HOST" --port "$PORT"
