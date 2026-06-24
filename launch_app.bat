@echo off
cd /d "%~dp0"

echo Starting Affiliate Clip Splicer...

if exist "venv\Scripts\python.exe" (
    set PYTHON_EXE=venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

start http://127.0.0.1:5050

%PYTHON_EXE% app.py

echo.
echo App stopped or an error occurred.
pause
