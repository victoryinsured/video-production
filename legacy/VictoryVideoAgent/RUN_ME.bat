@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo Victory Video Production Agent
echo ===============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Running setup first...
  call SETUP_WINDOWS.bat
  if errorlevel 1 goto error
)

call ".venv\Scripts\activate.bat"
python "agent\run_agent.py"
if errorlevel 1 goto error

echo.
echo Done. Open the output\review_package folder to review the finished files.
pause
exit /b 0

:error
echo.
echo The agent stopped because of an error. Check output\logs for details.
pause
exit /b 1
