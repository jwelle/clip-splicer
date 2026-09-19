#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAC_PACKAGES_DIR="mac_packages"

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
echo "Setting up Affiliate Clip Splicer..."
echo "Project folder: $(pwd)"

unset __PYVENV_LAUNCHER__ PYTHONHOME PYTHONPATH VIRTUAL_ENV
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v xattr >/dev/null 2>&1; then
  echo "Removing macOS quarantine attributes if present..."
  xattr -d com.apple.quarantine "$PROJECT_DIR" >/dev/null 2>&1 || true
fi

chmod +x setup_mac.command launch_app.command >/dev/null 2>&1 || true

if ! command -v python3 >/dev/null 2>&1; then
  fail "Python 3 was not found. Install Python 3, then run this setup again."
fi

PYTHON3_BIN="$(command -v python3)"
echo "Python: $($PYTHON3_BIN --version 2>&1)"

mkdir -p "$MAC_PACKAGES_DIR" || fail "Could not prepare the Mac package folder."
export PYTHONPATH="$PROJECT_DIR/$MAC_PACKAGES_DIR"

if [ -f "requirements.txt" ]; then
  echo "Installing requirements..."
  "$PYTHON3_BIN" -m pip install --upgrade --target "$MAC_PACKAGES_DIR" -r requirements.txt || fail "Could not install requirements.txt."
else
  echo "No requirements.txt found. Installing Flask and Werkzeug..."
  "$PYTHON3_BIN" -m pip install --upgrade --target "$MAC_PACKAGES_DIR" Flask Werkzeug || fail "Could not install Flask and Werkzeug."
fi

if ! "$PYTHON3_BIN" -c "import flask" >/dev/null 2>&1; then
  fail "Flask was not installed successfully."
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo ""
  echo "Setup finished for Python dependencies, but FFmpeg/FFprobe were not found."
  echo "Install them with Homebrew using: brew install ffmpeg"
else
  echo "FFmpeg: $(command -v ffmpeg)"
  echo "FFprobe: $(command -v ffprobe)"
fi

echo ""
echo "Setup complete."
echo "Next: double-click launch_app.command or Affiliate Clip Splicer.app to start the app."
echo "Local URL: http://127.0.0.1:5050"
pause_before_exit
