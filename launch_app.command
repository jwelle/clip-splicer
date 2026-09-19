#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_URL="http://127.0.0.1:5050"
APP_FILE="app.py"
MAC_PACKAGES_DIR="mac_packages"
LAUNCH_LOG="clipsplicer-launch.log"

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

exec > >(tee "$LAUNCH_LOG") 2>&1

clear
printf "Starting Affiliate Clip Splicer...\n"
printf "Project folder: %s\n" "$(pwd)"

unset __PYVENV_LAUNCHER__ PYTHONHOME PYTHONPATH VIRTUAL_ENV
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v xattr >/dev/null 2>&1; then
  echo "Removing macOS quarantine attributes if present..."
  xattr -d com.apple.quarantine "$PROJECT_DIR" >/dev/null 2>&1 || true
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

mkdir -p "$MAC_PACKAGES_DIR" || fail "Could not prepare the Mac package folder."
export PYTHONPATH="$PROJECT_DIR/$MAC_PACKAGES_DIR"

if ! "$PYTHON3_BIN" -c "import flask, werkzeug" >/dev/null 2>&1; then
  echo "Installing required Python packages..."
  if [ -f "requirements.txt" ]; then
    "$PYTHON3_BIN" -m pip install --upgrade --target "$MAC_PACKAGES_DIR" -r requirements.txt || fail "Could not install required Python packages."
  else
    "$PYTHON3_BIN" -m pip install --upgrade --target "$MAC_PACKAGES_DIR" Flask Werkzeug || fail "Could not install Flask and Werkzeug."
  fi
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

"$PYTHON3_BIN" "$APP_FILE" &
APP_PID=$!

for attempt in {1..40}; do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    echo "Opening $APP_URL ..."
    open "$APP_URL"
    echo ""
    echo "Affiliate Clip Splicer is running. Keep this Terminal window open while you use the app."
    echo "You can minimize it. Press Control+C here when you are done."
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
