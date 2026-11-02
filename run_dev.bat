@echo off
rem Run GHOSTNODE from source (development). Needs the .venv created by build.bat
rem or:  py -3.12 -m venv .venv  &&  .venv\Scripts\pip install -r requirements.txt
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Create it first:
    echo     py -3.12 -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)
".venv\Scripts\python.exe" -B main.py
