@echo off
echo ====================================
echo   Secure Data Portal - Startup
echo ====================================

cd /d "%~dp0"

echo.
echo [1/3] Setting up backend...
cd backend

if not exist .env (
  echo   No .env found - copying from .env.example
  echo   IMPORTANT: Edit backend\.env before production use
  copy .env.example .env
)

python -m venv .venv 2>nul
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

if not exist app\data\users.json (
  echo.
  echo   No admin user found - let's create one now.
  python -m app.seed_admin
)

echo   Starting FastAPI on :8000 ...
start cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
cd ..

timeout /t 4 /nobreak >nul

echo.
echo [2/3] Setting up frontend...
cd frontend
start cmd /k "npm install && npm run dev"
cd ..

timeout /t 5 /nobreak >nul

echo.
echo [3/3] Done!
echo ====================================
echo   Frontend:  http://localhost:3000
echo   API Docs:  http://localhost:8000/docs
echo ====================================
start http://localhost:3000
