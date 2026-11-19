@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ===============================================
echo Victory Video Production Agent Setup
echo ===============================================
echo.

py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 was not found.
  echo.
  echo Please install Python 3.12 64-bit from:
  echo https://www.python.org/downloads/release/python-31210/
  echo.
  echo During installation, check "Add python.exe to PATH".
  echo Then close this window and run SETUP_WINDOWS.bat again.
  echo.
  pause
  exit /b 1
)

echo Python version selected for this agent:
py -3.12 --version
echo.

if exist ".venv\Scripts\python.exe" (
  for /f "tokens=*" %%v in ('.venv\Scripts\python.exe --version 2^>nul') do set VENV_VERSION=%%v
  echo Existing virtual environment: %VENV_VERSION%
  echo %VENV_VERSION% | findstr /C:"Python 3.12" >nul
  if errorlevel 1 (
    echo Existing .venv is not Python 3.12. Rebuilding it now...
    rmdir /s /q ".venv"
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python 3.12 virtual environment...
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python --version
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist "config\config.json" copy "config\config.example.json" "config\config.json"

echo.
echo Setup complete.
echo All module scripts for Module 2 through Module 15 are included.
echo Next: double-click RUN_MODULE.bat to choose a module and run it.
pause
exit /b 0
