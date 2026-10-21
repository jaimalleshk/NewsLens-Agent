@echo off
title NewsLens - News ^& Analysis Agent
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo                 NewsLens - News ^& Analysis Agent Web App
echo ======================================================================
echo.
echo [1/3] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in your PATH. Please install Python 3.10+ or add it to PATH.
    pause
    exit /b 1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo [INFO] Stopping previous server instance on port 8000 ^(PID %%a^)...
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] Launching FastAPI Backend ^& Web Dashboard on http://localhost:8000 ...
echo [3/3] Browser will open automatically once the server is ready...
echo.

set NEWSLENS_OPEN_BROWSER=1
python -m backend.server

if errorlevel 1 (
    echo.
    echo [ERROR] Server terminated with an error.
    pause
)

