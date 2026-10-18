@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 start.py
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Bitte Python 3.10 oder neuer von https://www.python.org/downloads/windows/ installieren.
        pause
        exit /b 1
    )
    python start.py
)
if errorlevel 1 pause
