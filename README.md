# Affiliate Clip Splicer

Affiliate Clip Splicer is a small local web app that inserts a reusable promo clip into finished videos. Version 1 is designed for local use with FFmpeg and FFprobe.

## Requirements

- Python 3
- FFmpeg
- FFprobe
- A modern web browser

Supported video uploads:

- `.mp4`
- `.mov`
- `.m4v`

## Install FFmpeg

Mac users can install FFmpeg with Homebrew:

```bash
brew install ffmpeg
```

Windows users can install FFmpeg from:

```text
https://ffmpeg.org/download.html
```

After installing, confirm both tools are available:

```bash
ffmpeg -version
ffprobe -version
```

## Manual Setup

Go to the project folder:

```bash
cd ~/Desktop/clip-splicer
```

Create a virtual environment:

```bash
python3 -m venv venv
```

Mac/Linux activation:

```bash
source venv/bin/activate
```

Windows activation:

```bash
venv\Scripts\activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

Run app manually:

```bash
python app.py
```

Open browser:

```text
http://127.0.0.1:5050
```

## How to Launch the App

### Windows

First-time setup:

```text
Double-click setup_windows.bat
```

Launch after setup:

```text
Double-click launch_app.bat
```

### Mac

First-time setup from Terminal:

```bash
cd ~/Desktop/clip-splicer
chmod +x setup_mac.command
chmod +x launch_app.command
```

Then double-click:

```text
setup_mac.command
```

Launch after setup:

```text
launch_app.command
```

You can also run the scripts directly from Terminal:

```bash
./setup_mac.command
./launch_app.command
```

## Launching on Mac

The Mac launcher files are designed for the local project folder:

```bash
cd /Users/jonathanwelle/Desktop/clip-splicer
```

Run this once after downloading, moving, or repairing the project:

```bash
cd /Users/jonathanwelle/Desktop/clip-splicer
xattr -dr com.apple.quarantine .
chmod +x setup_mac.command launch_app.command
./setup_mac.command
```

After setup, launch the app by double-clicking either:

```text
launch_app.command
Affiliate Clip Splicer.app
```

The launcher opens the app here:

```text
http://127.0.0.1:5050
```

Keep the Terminal window open while using the app. Press `Control+C` in that Terminal window to stop the server.

If macOS blocks the launcher or says something is not permitted, run:

```bash
cd /Users/jonathanwelle/Desktop/clip-splicer
xattr -dr com.apple.quarantine .
chmod +x setup_mac.command launch_app.command
./setup_mac.command
```

If the virtual environment still fails, rebuild it:

```bash
cd /Users/jonathanwelle/Desktop/clip-splicer
rm -rf venv
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip

if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
else
  pip install Flask Werkzeug
fi
```

Then launch again:

```bash
./launch_app.command
```

## How to Use

1. Open the app at `http://127.0.0.1:5050`.
2. Upload the main video.
3. Upload the reusable promo clip.
4. Choose Beginning, End, or Custom timestamp.
5. If using Custom timestamp, enter seconds, `MM:SS`, or `HH:MM:SS`.
6. Click Generate Video.
7. Download the finished MP4 when processing completes.

Valid timestamp examples:

```text
0
15
30
90
01:15
03:45
00:04:15
```

## Troubleshooting

If FFmpeg or FFprobe is missing, install FFmpeg and confirm both commands work:

```bash
ffmpeg -version
ffprobe -version
```

If the app cannot read the duration of a video, try a different `.mp4`, `.mov`, or `.m4v` file and confirm FFprobe is installed correctly.

If a generated output is missing or empty, try a short test video first and check the terminal window for detailed FFmpeg output.

If Mac refuses to open a `.command` file, run:

```bash
chmod +x setup_mac.command
chmod +x launch_app.command
```

## Future Packaging Options

Version 1 uses clickable launcher scripts.

Future versions can be packaged as:

- Windows: `.exe` using PyInstaller
- Mac: `.app` bundle using PyInstaller or Platypus
- Installer: `.dmg` for Mac or `.msi`/`.exe` installer for Windows

FFmpeg and FFprobe may need to be bundled into the packaged version or installed separately.

## Planned Features

- Batch process multiple videos
- Save a default promo clip
- Add fade transitions before and after the promo clip
- Add affiliate disclosure text overlay
- Create presets for YouTube, Shorts, LinkedIn, and Instagram
- Create an optional intro/outro library
- Add drag-and-drop uploads
- Add progress bar
- Add preview thumbnails
- Remember last-used settings locally
- Package as Windows `.exe`
- Package as Mac `.app`
