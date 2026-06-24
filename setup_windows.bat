@echo off
cd /d "%~dp0"

echo Setting up Affiliate Clip Splicer...

python -m venv venv

call venv\Scripts\activate

pip install -r requirements.txt

echo.
echo Setup complete.
echo You can now double-click launch_app.bat to start the app.
pause
