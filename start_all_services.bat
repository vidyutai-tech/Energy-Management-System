@echo off
echo Starting Energy Management System with Load Optimization...
echo.

echo Starting Python API server...
start "Python API" cmd /k "cd python-backend && python start_api.py"

echo Waiting for Python API to start...
timeout /t 5 /nobreak > nul

echo Starting Node.js server...
start "Node.js Server" cmd /k "cd server && npm run dev"

echo Waiting for Node.js server to start...
timeout /t 5 /nobreak > nul

echo Starting React frontend...
start "React Frontend" cmd /k "cd client && npm run dev"

echo.
echo All services are starting up...
echo.
echo Services will be available at:
echo - Python API: http://localhost:8000
echo - Node.js API: http://localhost:3000
echo - React Frontend: http://localhost:5173
echo.
echo Press any key to run integration test...
pause > nul

echo Running integration test...
node test_integration.js

echo.
echo Press any key to exit...
pause > nul
