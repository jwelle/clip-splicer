@echo off
setlocal
cd /d "%~dp0"

echo Starting Affiliate Clip Splicer...

if exist "venv\Scripts\python.exe" (
    set PYTHON_EXE=venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: FFmpeg was not found on PATH.
    echo Install FFmpeg with: winget install --id Gyan.FFmpeg -e
    pause
    exit /b 1
)

where ffprobe >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: FFprobe was not found on PATH.
    echo Install FFmpeg with: winget install --id Gyan.FFmpeg -e
    pause
    exit /b 1
)

start "" http://127.0.0.1:5050

"%PYTHON_EXE%" app.py

echo.
echo App stopped or an error occurred.
pause
