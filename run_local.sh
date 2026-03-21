#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Activate Python venv
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r backend/requirements.txt
else
    . .venv/bin/activate
fi

# Install frontend deps if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Seed database if empty
if [ ! -f "backend/quiz.db" ]; then
    echo "Seeding database..."
    python scripts/seed_data.py
fi

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

# Start backend
echo "Starting backend on http://localhost:8000 ..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend on http://localhost:5173 ..."
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

echo ""
echo "============================================"
echo "  Quiz Core is running!"
echo "  Frontend:  http://localhost:5173"
echo "  Backend:   http://localhost:8000/docs"
echo ""
echo "  Teacher:   teacher / teacher123"
echo "  Student:   student01 / quiz2026"
echo "============================================"
echo "  Press Ctrl+C to stop"
echo ""

wait
