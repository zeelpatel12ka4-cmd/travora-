@echo off
echo === Starting Travora Frontend Server ===
echo.
echo Frontend will be available at: http://localhost:5500
echo.
echo Press Ctrl+C to stop.
echo.
cd travora-frontend
python -m http.server 5500
pause
