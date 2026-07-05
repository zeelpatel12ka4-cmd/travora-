@echo off
echo === Starting Travora Backend Server ===
echo.
echo API will be available at: http://localhost:8000
echo API docs at:              http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo.
venv\Scripts\uvicorn.exe main:app --reload --host 0.0.0.0 --port 8000
pause
