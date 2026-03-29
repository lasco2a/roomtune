#!/usr/bin/env bash
# RoomTune - start both backend and frontend dev servers
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== RoomTune ==="
echo ""

# Start backend
echo "Starting backend (FastAPI) on http://localhost:8001 …"
(cd "$SCRIPT_DIR" && python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload) &
BACKEND_PID=$!

# Start frontend (if node_modules exist)
if [ -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    echo "Starting frontend (Vite) on http://localhost:5173 …"
    (cd "$SCRIPT_DIR/frontend" && npm run dev) &
    FRONTEND_PID=$!
else
    echo "Frontend not installed yet. Run: cd frontend && npm install && npm run dev"
    FRONTEND_PID=""
fi

echo ""
echo "Backend PID: $BACKEND_PID"
[ -n "$FRONTEND_PID" ] && echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop."

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down …"
    kill $BACKEND_PID 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null || true
    wait
}
trap cleanup EXIT INT TERM

wait
