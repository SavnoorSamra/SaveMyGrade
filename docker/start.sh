#!/usr/bin/env bash
set -euo pipefail

# Backend supports GOOGLE_API_KEY or GEMINI_API_KEY.
if [[ -n "${GEMINI_API_KEY:-}" && -z "${GOOGLE_API_KEY:-}" ]]; then
  export GOOGLE_API_KEY="${GEMINI_API_KEY}"
fi

python3 /app/backend/app.py &
BACK_PID=$!

cd /app/frontend
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONT_PID=$!

cleanup() {
  kill "${BACK_PID}" "${FRONT_PID}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# Exit when either process exits, then clean up the other.
wait -n "${BACK_PID}" "${FRONT_PID}"
cleanup
