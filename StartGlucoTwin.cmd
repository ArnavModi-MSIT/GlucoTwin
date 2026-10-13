@echo off
setlocal
title GlucoTwin local dashboard
cd /d "%~dp0arnavmodi23_MSIT"
if errorlevel 1 goto missing_project
if not exist "scripts\launch_dashboard.py" goto missing_project

if exist ".venv\Scripts\python.exe" (
    set "GLUCOTWIN_PYTHON=%CD%\.venv\Scripts\python.exe"
    goto run_python
)
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
    set "GLUCOTWIN_PYTHON=%LocalAppData%\Programs\Python\Python310\python.exe"
    goto run_python
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3.10 -c "import sys" >nul 2>nul
    if not errorlevel 1 goto run_py
)
where python >nul 2>nul
if not errorlevel 1 (
    set "GLUCOTWIN_PYTHON=python"
    goto run_python
)
echo Python was not found. Install Python 3.10 or later, then follow the repository README.md.
goto failed

:run_py
py -3.10 "scripts\launch_dashboard.py" %*
goto finished

:run_python
"%GLUCOTWIN_PYTHON%" "scripts\launch_dashboard.py" %*
goto finished

:missing_project
echo Project files were not found. Keep this launcher beside the arnavmodi23_MSIT folder.
goto failed

:finished
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo Dashboard did not start. Read the message above for the required setup.
pause
exit /b 1
