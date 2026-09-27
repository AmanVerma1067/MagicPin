#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
echo "==> Starting Vera Engine locally on port ${PORT}..."
echo "==> Interactive Dashboard UI: http://localhost:${PORT}/"
echo "==> Swagger API Documentation: http://localhost:${PORT}/docs"
echo "==> Health check: http://localhost:${PORT}/v1/healthz"
export PYTHONPATH=.

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
