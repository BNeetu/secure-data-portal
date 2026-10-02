#!/bin/bash
set -e
echo "===================================="
echo "  Secure Data Portal — Startup"
echo "===================================="

cd "$(dirname "$0")"

# ── Backend ──
echo ""
echo "[1/3] Setting up backend..."
cd backend

if [ ! -f .env ]; then
  echo "  No .env found — copying from .env.example"
  echo "  ⚠️  Edit backend/.env before production use (JWT_SECRET, ALLOWED_IPS, etc.)"
  cp .env.example .env
fi

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt -q

if [ ! -f app/data/users.json ]; then
  echo ""
  echo "  No admin user found — let's create one now."
  python3 -m app.seed_admin
fi

echo "  Starting FastAPI on :8000 ..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

sleep 3

# ── Frontend ──
echo ""
echo "[2/3] Setting up frontend..."
cd frontend
npm install --silent
echo "  Starting Vite dev server on :3000 ..."
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo ""
echo "[3/3] Done!"
echo "===================================="
echo "  Frontend:  http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Press Ctrl+C to stop both servers"
echo "===================================="

if command -v xdg-open &> /dev/null; then xdg-open http://localhost:3000
elif command -v open &> /dev/null; then open http://localhost:3000
fi

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'; exit" INT
wait
