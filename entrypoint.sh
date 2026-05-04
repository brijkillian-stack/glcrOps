#!/bin/bash
# Single entrypoint for the Render container.
# Starts the Reflex backend (FastAPI on :8000) and Caddy (listening on $PORT).
# Caddy serves the pre-exported static frontend from /app/.web/_static and
# reverse-proxies /_event/* paths to the backend.
#
# Uses `bash` (not `sh`) because we need `wait -n`.

set -eu

: "${PORT:=10000}"
export PORT

echo "[entrypoint] starting Reflex backend on :8000"
reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port 8000 &
REFLEX_PID=$!

# Give Reflex a beat to come up before Caddy starts proxying.
sleep 4

echo "[entrypoint] starting Caddy on :$PORT"
caddy run --config /app/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# Exit when whichever process dies first; Render handles the restart.
wait -n "$REFLEX_PID" "$CADDY_PID"
EXIT_CODE=$?
echo "[entrypoint] one process exited (code=$EXIT_CODE) — shutting down"
kill "$REFLEX_PID" "$CADDY_PID" 2>/dev/null || true
exit "$EXIT_CODE"
