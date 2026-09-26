#!/usr/bin/env bash
set -euo pipefail

echo "==> Starting Vera Engine locally on port 8000..."
export PYTHONPATH=.
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
