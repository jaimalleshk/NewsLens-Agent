@echo off
title NewsLens - News Agent Console CLI
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo             NewsLens - Interactive Console CLI & Dialogue
echo ======================================================================
echo.
python -m cli.main chat

if errorlevel 1 (
    echo.
    pause
)
