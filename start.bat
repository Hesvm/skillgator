@echo off
title AI Ecosystem Live Monitor
cd /d "%~dp0"
echo ========================================================
echo   Launching AI Ecosystem Live Monitor (Antigravity & Claude)
echo ========================================================
start "" http://localhost:4949
python server.py
pause
