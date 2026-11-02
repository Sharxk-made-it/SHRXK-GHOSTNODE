@echo off
rem ============================================================
rem  GHOSTNODE - build the portable package
rem  Run on a Windows 10/11 x64 PC with Python 3.11 or 3.12 (x64).
rem  Output: dist\GHOSTNODE\  (copy this whole folder to your USB)
rem ============================================================
setlocal
cd /d "%~dp0"

echo [GHOSTNODE] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Could not create the virtual environment. Is Python 3.11/3.12 x64 installed?
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    exit /b 1
)

echo [GHOSTNODE] Running core tests...
python -B -m unittest discover -s tests -t .
if errorlevel 1 (
    echo [ERROR] Tests failed - build aborted.
    exit /b 1
)

echo [GHOSTNODE] Building executable...
pyinstaller --noconfirm --clean GHOSTNODE.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

rem Pre-create the data folders so the package matches the documented layout.
mkdir "dist\GHOSTNODE\data"   2>nul
mkdir "dist\GHOSTNODE\config" 2>nul
mkdir "dist\GHOSTNODE\logs"   2>nul

echo.
echo [GHOSTNODE] Done. Copy the folder  dist\GHOSTNODE  to your USB drive.
echo             Run it with  GHOSTNODE\GHOSTNODE.exe
endlocal
