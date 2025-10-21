#!/bin/bash

echo "Starting Energy Management System with Load Optimization..."
echo

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo "Port $1 is already in use. Please stop the service using this port."
        exit 1
    fi
}

# Check ports
check_port 8000
check_port 3000
check_port 5173

echo "Starting Python API server..."
cd python-backend
python start_api.py &
PYTHON_PID=$!
cd ..

echo "Waiting for Python API to start..."
sleep 5

echo "Starting Node.js server..."
cd server
npm run dev &
NODE_PID=$!
cd ..

echo "Waiting for Node.js server to start..."
sleep 5

echo "Starting React frontend..."
cd client
npm run dev &
REACT_PID=$!
cd ..

echo
echo "All services are starting up..."
echo
echo "Services will be available at:"
echo "- Python API: http://localhost:8000"
echo "- Node.js API: http://localhost:3000"
echo "- React Frontend: http://localhost:5173"
echo

# Wait for user input
read -p "Press Enter to run integration test..."

echo "Running integration test..."
node test_integration.js

echo
echo "Services are running in the background."
echo "To stop all services, run: kill $PYTHON_PID $NODE_PID $REACT_PID"
echo
echo "Press Ctrl+C to exit this script (services will continue running)"
wait
