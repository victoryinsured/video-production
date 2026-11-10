@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
chcp 65001 >nul

echo ===============================================
echo Victory Video Production Agent - Choose Module
echo ===============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Running setup first...
  call SETUP_WINDOWS.bat
  if errorlevel 1 goto error
)

call ".venv\Scripts\activate.bat"

echo First, choose which module you want to produce.
echo The package includes Module 2 through Module 15.
echo.
python "agent\select_module.py"
if errorlevel 1 goto error

echo.
echo Starting video production for the selected module...
echo.
python "agent\run_agent.py"
if errorlevel 1 goto error

echo.
echo Done. Open the output\review_package folder to review the finished files.
echo You can run RUN_MODULE.bat again later to choose another module.
pause
exit /b 0

:error
echo.
echo The agent stopped because of an error.
echo If setup failed, confirm Python 3.12 is installed and try SETUP_WINDOWS.bat again.
echo If production failed, check output\logs for details.
pause
exit /b 1
