@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "TASK_PYTHON=python"
) else (
  set "TASK_PYTHON=py -3"
)
%TASK_PYTHON% -m venv .venv
if errorlevel 1 goto failure
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failure
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failure
.venv\Scripts\python.exe scrape_stoletnika.py --refresh
if errorlevel 1 goto failure
echo Done. Open the output folder and check review.csv.
start "" output
pause
exit /b 0
:failure
echo Failed. Read the error above and output\network_diagnostics.json if present.
pause
exit /b 1
