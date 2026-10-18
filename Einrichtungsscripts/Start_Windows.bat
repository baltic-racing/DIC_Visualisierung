@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows.ps1" -Launch
set "DIC_EXIT=%ERRORLEVEL%"
if not "%DIC_EXIT%"=="0" pause
exit /b %DIC_EXIT%
