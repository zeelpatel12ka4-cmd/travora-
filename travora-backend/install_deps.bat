@echo off
echo === Installing Travora dependencies ===
echo This may take a few minutes...
echo.
venv\Scripts\pip.exe install fastapi==0.111.0
venv\Scripts\pip.exe install "uvicorn[standard]==0.29.0"
venv\Scripts\pip.exe install motor==3.4.0
venv\Scripts\pip.exe install pymongo==4.7.2
venv\Scripts\pip.exe install "pydantic[email]==2.7.1"
venv\Scripts\pip.exe install "python-jose[cryptography]==3.3.0"
venv\Scripts\pip.exe install "passlib[bcrypt]==1.7.4"
venv\Scripts\pip.exe install python-dotenv==1.0.1
venv\Scripts\pip.exe install anthropic==0.26.0
venv\Scripts\pip.exe install httpx==0.27.0
echo.
echo === All dependencies installed! ===
echo.
echo Now run: start_server.bat
pause
