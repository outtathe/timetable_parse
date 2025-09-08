#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
echo "Done. Activate venv with: source .venv/bin/activate"
