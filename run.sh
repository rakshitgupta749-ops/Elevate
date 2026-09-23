#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

echo "Starting Backend server..."
cd backend
uvicorn app.main:app --reload &
BACKEND_PID=$!
cd ..

echo "Starting Frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\nBoth servers are running."
echo "Backend: http://127.0.0.1:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both servers."

# Trap termination signals to kill both processes when the script stops
trap "echo 'Shutting down servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGINT SIGTERM EXIT

# Wait indefinitely so the script doesn't exit immediately
wait
