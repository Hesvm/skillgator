# AI Ecosystem Live Monitor Launcher
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " 🚀 AI Ecosystem Live Monitor (Antigravity & Claude)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

Start-Process "http://localhost:4949"
python server.py
