#!/usr/bin/env bash
# One-shot local setup for the Self-Healing Code Sandbox.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

if [[ ! -d .venv ]]; then
  echo "==> Creating virtualenv (.venv)"
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt pytest httpx >/dev/null

if [[ ! -f .env ]]; then
  echo "==> Writing .env from .env.example (mock mode by default)"
  cp .env.example .env
  # Ensure demo works without a real OpenAI key.
  if ! grep -q '^MOCK_LLM=' .env; then
    echo 'MOCK_LLM=true' >> .env
  else
    sed -i 's/^MOCK_LLM=.*/MOCK_LLM=true/' .env
  fi
fi

echo "==> Running test suite"
pytest

echo
echo "Setup complete."
echo "  Activate:  source .venv/bin/activate"
echo "  Serve UI:  python main.py serve"
echo "  One-shot:  python main.py run \"Write a function add(a, b)\""
echo "  Open:      http://127.0.0.1:43127"
