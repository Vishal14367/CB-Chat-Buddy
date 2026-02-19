@echo off
echo ========================================
echo Course Buddy Bot - Quick Start
echo ========================================
echo.
echo This will start both backend and frontend servers.
echo.
echo Make sure you have:
echo - Python 3.9+ installed
echo - Node.js 18+ installed
echo - Run setup first (see SETUP_GUIDE.md)
echo.
pause
echo.

echo Starting Backend Server...
start cmd /k "cd backend && echo Backend Server && python main.py"

timeout /t 5 /nobreak > nul

echo Starting Frontend Server...
start cmd /k "cd frontend && echo Frontend Server && npm run dev"

echo.
echo ========================================
echo Servers Starting!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Two new terminal windows should open.
echo Close this window or press Ctrl+C
echo.
pause
