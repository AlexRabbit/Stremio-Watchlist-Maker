@echo off
setlocal EnableDelayedExpansion
title Stremio Watchlist Maker
cd /d "%~dp0"

echo ========================================
echo  Stremio Watchlist Maker  v0.5
echo ========================================
echo.

:: --- Python check ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from https://www.python.org/
    goto :end
)

:: --- Stop stale server on port 7010 ---
echo [RUN] Stopping any old server on port 7010...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":7010" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: --- Virtual environment ---
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :end
)

set PY=.venv\Scripts\python.exe

echo [SETUP] Installing dependencies...
"%PY%" -m pip install -q --upgrade pip
"%PY%" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed
    goto :end
)

:: --- .env ---
if not exist ".env" (
    echo [SETUP] Creating .env from .env.example
    copy /Y ".env.example" ".env" >nul
)

:: --- Directories ---
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo [RUN] Starting server at http://127.0.0.1:7010/configure
echo       Health check: http://127.0.0.1:7010/api/health  (must show version 0.5.1)
echo.

"%PY%" main.py
set EXIT_CODE=%ERRORLEVEL%

:end
echo.
echo Exit code: %EXIT_CODE%
echo Press any key to close...
pause >nul
