#!/usr/bin/fish

# Run from the repo root regardless of where the script is invoked from.
cd (status dirname)/..

set -q PORT; or set -l PORT 8000

# Gracefully terminate any existing process holding the port to prevent [Errno 98]
if type -q lsof
    set -l existing_pids (lsof -ti :$PORT 2>/dev/null)
    if test -n "$existing_pids"
        echo "==> Port $PORT already in use by PID $existing_pids. Freeing port..."
        kill -9 $existing_pids 2>/dev/null
        sleep 1
    end
else if type -q fuser
    fuser -k $PORT/tcp 2>/dev/null
    sleep 1
end

echo "==> Starting Vera Engine locally on port $PORT..."
echo "==> Interactive Dashboard UI: http://localhost:$PORT/"
echo "==> Swagger API Documentation: http://localhost:$PORT/docs"
echo "==> Health check: http://localhost:$PORT/v1/healthz"
set -x PYTHONPATH .

if test -f .venv/bin/activate.fish
    source .venv/bin/activate.fish
end

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
