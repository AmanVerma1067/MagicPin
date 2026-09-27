#!/usr/bin/fish

# Run from the repo root regardless of where the script is invoked from.
cd (status dirname)/..

set -q PORT; or set -l PORT 8000
echo "==> Starting Vera Engine locally on port $PORT..."
echo "==> Interactive Dashboard UI: http://localhost:$PORT/"
echo "==> Swagger API Documentation: http://localhost:$PORT/docs"
echo "==> Health check: http://localhost:$PORT/v1/healthz"
set -x PYTHONPATH .

if test -f .venv/bin/activate.fish
    source .venv/bin/activate.fish
end

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
