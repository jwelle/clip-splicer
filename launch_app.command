#!/bin/bash

PROJECT_DIR="/Users/jonathanwelle/Desktop/clip-splicer"
APP_URL="http://127.0.0.1:5050"
APP_FILE="app.py"
VENV_DIR="venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

pause_before_exit() {
  echo ""
  read -p "Press Enter to close this window..."
}

fail() {
  echo ""
  echo "ERROR: $1"
  pause_before_exit
  exit 1
}

cd "$PROJECT_DIR" || fail "Could not open project folder: $PROJECT_DIR"

clear
printf "Starting Affiliate Clip Splicer...\n"
printf "Project folder: %s\n" "$(pwd)"

unset __PYVENV_LAUNCHER__
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v xattr >/dev/null 2>&1; then
  echo "Removing macOS quarantine attributes if present..."
  xattr -dr com.apple.quarantine "$PROJECT_DIR" >/dev/null 2>&1 || true
fi

chmod +x setup_mac.command launch_app.command >/dev/null 2>&1 || true

if ! command -v python3 >/dev/null 2>&1; then
  fail "Python 3 was not found. Install Python 3, then run setup_mac.command again."
fi

PYTHON3_BIN="$(command -v python3)"
echo "Python: $($PYTHON3_BIN --version 2>&1)"

if [ ! -f "$APP_FILE" ]; then
  fail "Could not find $APP_FILE in $PROJECT_DIR."
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Virtual environment not found. Creating it now..."
  "$PYTHON3_BIN" -m venv "$VENV_DIR" || fail "Could not create the virtual environment."
fi

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$VENV_DIR" >/dev/null 2>&1 || true
fi

if [ ! -x "$VENV_PYTHON" ]; then
  fail "The virtual environment is missing $VENV_PYTHON. Run setup_mac.command to repair it."
fi

if [ ! -x "$VENV_PIP" ]; then
  fail "The virtual environment is missing $VENV_PIP. Run setup_mac.command to repair it."
fi

"$VENV_PYTHON" -m pip install --upgrade pip || fail "Could not upgrade pip."

if [ -f "requirements.txt" ]; then
  echo "Installing requirements..."
  "$VENV_PYTHON" -m pip install -r requirements.txt || fail "Could not install requirements.txt."
else
  echo "No requirements.txt found. Installing Flask and Werkzeug..."
  "$VENV_PYTHON" -m pip install Flask Werkzeug || fail "Could not install Flask and Werkzeug."
fi

if ! "$VENV_PYTHON" -c "import flask" >/dev/null 2>&1; then
  fail "Flask is still not available inside the virtual environment. Run setup_mac.command again."
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  fail "FFmpeg was not found. Install it with Homebrew using: brew install ffmpeg"
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  fail "FFprobe was not found. Install FFmpeg with Homebrew using: brew install ffmpeg"
fi

echo "FFmpeg: $(command -v ffmpeg)"
echo "FFprobe: $(command -v ffprobe)"
echo ""
echo "Starting Flask server..."

"$VENV_PYTHON" "$APP_FILE" &
APP_PID=$!

for attempt in {1..40}; do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    echo "Opening $APP_URL ..."
    open "$APP_URL"
    echo ""
    echo "Affiliate Clip Splicer is running. Leave this Terminal window open while you use the app."
    echo "Press Control+C to stop the server."
    wait "$APP_PID"
    APP_STATUS=$?
    echo ""
    echo "App stopped."
    pause_before_exit
    exit "$APP_STATUS"
  fi

  if ! kill -0 "$APP_PID" >/dev/null 2>&1; then
    echo ""
    echo "The app stopped before it was ready. Check the messages above for details."
    pause_before_exit
    exit 1
  fi

  sleep 0.5
done

echo ""
echo "The app did not become ready at $APP_URL."
kill "$APP_PID" >/dev/null 2>&1 || true
pause_before_exit
exit 1
