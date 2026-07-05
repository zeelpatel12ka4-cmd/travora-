@echo off
echo === Travora Backend Setup ===
echo.

echo [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create venv
    pause
    exit /b 1
)
echo Done.

echo [2/3] Installing dependencies...
venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)
echo Done.

echo [3/3] Copying .env file...
if not exist .env (
    copy .env.example .env
    echo .env created - please edit it with your API keys
) else (
    echo .env already exists - skipping
)

echo.
echo === Setup complete! ===
echo.
echo Next steps:
echo  1. Edit .env and add your ANTHROPIC_API_KEY
echo  2. Run: start_server.bat
echo.
pause
