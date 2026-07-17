@echo off
setlocal
cd /d "%~dp0"

echo Setting up Affiliate Clip Splicer...

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found on PATH. Install Python 3, then run this setup again.
    pause
    exit /b 1
)

python -m venv venv
if errorlevel 1 (
    echo.
    echo ERROR: Could not create the virtual environment.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo ERROR: The virtual environment was not created correctly.
    pause
    exit /b 1
)

"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo ERROR: Could not upgrade pip.
    pause
    exit /b 1
)

"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Could not install requirements.txt.
    pause
    exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo Setup finished for Python dependencies, but FFmpeg was not found.
    echo Install FFmpeg with: winget install --id Gyan.FFmpeg -e
    goto complete
)

where ffprobe >nul 2>nul
if errorlevel 1 (
    echo.
    echo Setup finished for Python dependencies, but FFprobe was not found.
    echo Install FFmpeg with: winget install --id Gyan.FFmpeg -e
    goto complete
)

echo FFmpeg and FFprobe were found on PATH.

:complete
echo.
echo Setup complete.
echo You can now double-click launch_app.bat to start the app.
pause
