#!/usr/bin/env bash
# Idempotent Cloud Agent install for Self-Healing Code Sandbox.
set -euo pipefail
cd /workspace

if ! python3 -c 'import venv' 2>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv python3-pip
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
