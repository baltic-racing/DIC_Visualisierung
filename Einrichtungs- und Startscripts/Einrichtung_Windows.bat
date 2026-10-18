@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows.ps1" -Setup
set "DIC_EXIT=%ERRORLEVEL%"
pause
exit /b %DIC_EXIT%
