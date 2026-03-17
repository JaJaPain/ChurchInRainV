@echo off
TITLE AVizualizer — Cathedral in the Storm
SETLOCAL

SET "PROJECT_DIR=D:\AVizualizer"

echo ==========================================
echo   AVizualizer - Modern Christian Rock
echo   Cathedral in the Storm Edition
echo ==========================================
echo.

D:
cd /d "%PROJECT_DIR%"

if not exist "venv\Scripts\python.exe" (
    echo [SETUP] Virtual environment not found. Creating...
    python -m venv venv
    echo [SETUP] Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
    echo [SETUP] Done!
    echo.
)

echo [STATUS] Launching AVizualizer...
"venv\Scripts\python.exe" main.py

echo.
echo [STATUS] AVizualizer exited.
pause
