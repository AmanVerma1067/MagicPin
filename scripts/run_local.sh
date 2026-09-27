#!/usr/bin/env bash
set -euo pipefail

# Run from the repo root regardless of where the script is invoked from.
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"

# Gracefully terminate any existing process holding the port to prevent [Errno 98]
if command -v lsof >/dev/null 2>&1; then
    EXISTING_PIDS=$(lsof -ti :"${PORT}" 2>/dev/null || true)
    if [ -n "${EXISTING_PIDS}" ]; then
        echo "==> Port ${PORT} already in use by PID ${EXISTING_PIDS}. Freeing port..."
        kill -9 ${EXISTING_PIDS} 2>/dev/null || true
        sleep 1
    fi
elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}"/tcp 2>/dev/null || true
    sleep 1
fi

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
