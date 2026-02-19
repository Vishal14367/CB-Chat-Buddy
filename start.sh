#!/bin/bash

echo "========================================"
echo "Course Buddy Bot - Quick Start"
echo "========================================"
echo ""
echo "This will start both backend and frontend servers."
echo ""
echo "Make sure you have:"
echo "- Python 3.9+ installed"
echo "- Node.js 18+ installed"
echo "- Run setup first (see SETUP_GUIDE.md)"
echo ""
read -p "Press Enter to continue..."
echo ""

# Start backend in background
echo "Starting Backend Server..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 5

# Start frontend in background
echo "Starting Frontend Server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================"
echo "Servers Started!"
echo "========================================"
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
