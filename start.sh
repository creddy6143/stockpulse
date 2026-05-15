#!/bin/bash
# StockPulse startup script

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting StockPulse..."

# Backend
cd "$ROOT/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID (port 8000)"

# Wait for backend
sleep 3

# Frontend
cd "$ROOT/frontend"
PORT=3002 BROWSER=none npm start &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID (port 3002)"

echo ""
echo "StockPulse is starting..."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3002"
echo ""
echo "Press Ctrl+C to stop both services"

# Trap to clean up both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT

wait
