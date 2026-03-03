@echo off
set "REPO_ROOT=%~dp0"
set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "VENV_PY=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Run install.bat first to create the virtual environment.
    pause
    exit /b 1
)

"%VENV_PY%" "%REPO_ROOT%\gui\app.py" %*
if %ERRORLEVEL% neq 0 pause
