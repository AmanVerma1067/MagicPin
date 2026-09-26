#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8001}"
echo "==> Starting Vera Engine locally on port ${PORT}..."
echo "==> Interactive Dashboard UI: http://localhost:${PORT}/"
echo "==> Swagger API Documentation: http://localhost:${PORT}/docs"
export PYTHONPATH=.
exec .venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1

