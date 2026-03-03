@echo off
setlocal EnableDelayedExpansion
title extract-xiso WebUI - Windows Installer

:: Repo root (directory where this batch file lives)
set "REPO_ROOT=%~dp0"
set "REPO_ROOT=%REPO_ROOT:~0,-1%"

echo.
echo   [extract-xiso WebUI] Windows Installer
echo   --------------------------------------
echo.

:: 1. Find Python 3.8+
set "PYTHON="
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%v in ('py -3 -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2^>nul') do set "VER=%%v"
    if defined VER (
        echo [OK] Found Python via py -3
        set "PYTHON=py -3"
    )
)
if not defined PYTHON (
    for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2^>nul') do set "VER=%%v"
    if defined VER (
        echo [OK] Found Python via python
        set "PYTHON=python"
    )
)
if not defined PYTHON (
    echo [ERROR] Python 3.8+ not found. Install from https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Create venv if missing
set "VENV=%REPO_ROOT%\.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"
set "VENV_PIP=%VENV%\Scripts\pip.exe"

if not exist "%VENV_PY%" (
    echo.
    echo [INFO] Creating virtual environment in .venv ...
    "%PYTHON%" -m venv "%VENV%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create venv. Try: pip install virtualenv
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: 3. Install Python dependencies
echo.
echo [INFO] Installing Python dependencies (Flask, etc.) ...
"%VENV_PIP%" install --upgrade pip -q
"%VENV_PIP%" install -r "%REPO_ROOT%\gui\requirements.txt" -q
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] Python dependencies installed.

:: 4. Create bin for optional tools
if not exist "%REPO_ROOT%\bin" mkdir "%REPO_ROOT%\bin"
echo [OK] bin\ directory ready.

:: 5. Build extract-xiso if CMake is available
set "BUILD_DIR=%REPO_ROOT%\build"
set "EXE_RELEASE=%BUILD_DIR%\Release\extract-xiso.exe"
set "EXE_ROOT=%BUILD_DIR%\extract-xiso.exe"

if exist "%EXE_RELEASE%" (
    echo [OK] extract-xiso.exe already built.
) else if exist "%EXE_ROOT%" (
    echo [OK] extract-xiso.exe already built.
) else (
    where cmake >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo.
        echo [INFO] Building extract-xiso (C binary) ...
        if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
        cd /d "%BUILD_DIR%"
        cmake .. -DCMAKE_BUILD_TYPE=Release
        if !ERRORLEVEL! equ 0 (
            cmake --build . --config Release
            if !ERRORLEVEL! equ 0 (
                echo [OK] extract-xiso built successfully.
            ) else (
                echo [WARN] Build failed. GUI will run but Extract/Create/List/Rewrite need the binary.
                echo        Install Visual Studio Build Tools or download a release from GitHub.
            )
        ) else (
            echo [WARN] CMake configure failed. GUI will run; core features need extract-xiso.exe.
        )
        cd /d "%REPO_ROOT%"
    ) else (
        echo [WARN] CMake not found. GUI will run; install Visual Studio Build Tools to build extract-xiso.
    )
)

:: 6. Create run.bat (%% becomes % in the generated file)
set "RUN_BAT=%REPO_ROOT%\run.bat"
(
echo @echo off
echo set "REPO_ROOT=%%~dp0"
echo set "REPO_ROOT=%%REPO_ROOT:~0,-1%%"
echo "%%REPO_ROOT%%\.venv\Scripts\python.exe" "%%REPO_ROOT%%\gui\app.py" %%*
echo if "%%ERRORLEVEL%%" neq "0" pause
) > "%RUN_BAT%"
echo [OK] Created run.bat

echo.
echo   --------------------------------------
echo   Installation complete!
echo.
echo   Start the WebUI:
echo     run.bat
echo   or:
echo     .venv\Scripts\python.exe gui\app.py
echo.
echo   Then open:  http://localhost:7860
echo   (browser opens automatically)
echo.
pause
