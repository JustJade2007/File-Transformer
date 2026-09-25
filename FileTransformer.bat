@echo off
cd /d "%~dp0"
if "%~1"=="" (
    start "" pythonw main.py
) else (
    python main.py %*
)

