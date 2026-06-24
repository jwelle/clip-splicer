#!/bin/bash

PROJECT_DIR="/Users/jonathanwelle/Desktop/clip-splicer"
VENV_DIR="venv"
VENV_PYTHON="$VENV_DIR/bin/python"

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

unset __PYVENV_LAUNCHER__
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v xattr >/dev/null 2>&1; then
  echo "Removing macOS quarantine attributes if present..."
  xattr -dr com.apple.quarantine "$PROJECT_DIR" >/dev/null 2>&1 || true
fi

chmod +x setup_mac.command launch_app.command >/dev/null 2>&1 || true

if ! command -v python3 >/dev/null 2>&1; then
  fail "Python 3 was not found. Install Python 3, then run this setup again."
fi

PYTHON3_BIN="$(command -v python3)"
echo "Python: $($PYTHON3_BIN --version 2>&1)"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  "$PYTHON3_BIN" -m venv "$VENV_DIR" || fail "Could not create the virtual environment."
elif [ ! -x "$VENV_PYTHON" ]; then
  echo "The existing virtual environment looks incomplete. Recreating it..."
  mv "$VENV_DIR" "venv_broken_$(date +%Y%m%d_%H%M%S)" || fail "Could not move the broken virtual environment aside."
  "$PYTHON3_BIN" -m venv "$VENV_DIR" || fail "Could not recreate the virtual environment."
else
  echo "Virtual environment already exists."
fi

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$VENV_DIR" >/dev/null 2>&1 || true
fi

if [ ! -x "$VENV_PYTHON" ]; then
  fail "The virtual environment could not be prepared correctly."
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
