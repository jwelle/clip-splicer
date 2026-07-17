# Affiliate Clip Splicer

Affiliate Clip Splicer is a small local Flask web app that inserts a reusable promo clip into finished videos. It runs locally on macOS and Windows and uses FFmpeg/FFprobe from your system `PATH`.

## Requirements

- Python 3
- FFmpeg and FFprobe
- A modern web browser

Supported video uploads:

- `.mp4`
- `.mov`
- `.m4v`

## Install FFmpeg

macOS:

```bash
brew install ffmpeg
```

Windows PowerShell:

```powershell
winget install --id Gyan.FFmpeg -e
```

After installing, open a new terminal and confirm both tools are available:

```bash
ffmpeg -version
ffprobe -version
```

## macOS Setup and Run

From the project folder:

```bash
cd ~/Desktop/clip-splicer
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5050
```

You can also use the Mac launch helpers:

```bash
cd ~/Desktop/clip-splicer
xattr -dr com.apple.quarantine .
chmod +x setup_mac.command launch_app.command
./setup_mac.command
./launch_app.command
```

After setup, double-clicking `launch_app.command` or `Affiliate Clip Splicer.app` should also work.

## Windows Setup and Run

From Windows PowerShell:

```powershell
cd "$HOME\Desktop\clip-splicer"
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

Then open:

```text
http://127.0.0.1:5050
```

You can also double-click:

```text
setup_windows.bat
launch_app.bat
```

## How to Use

1. Open the app at `http://127.0.0.1:5050`.
2. Optionally select, upload once, or save an Intro.
3. Upload the main video.
4. Optionally select, upload once, or save a Promo clip, then choose Beginning, End, or Custom timestamp.
5. Optionally select, upload once, or save an Outro.
6. Click Generate Video and download the finished MP4 when processing completes.

The resulting order is Intro + Main Video + Outro. A promo at the beginning is placed after the intro; a promo at the end is placed before the outro; a custom promo is inserted into the main video before the outro.

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

If the app says FFmpeg or FFprobe is missing, install FFmpeg with the command for your operating system above, then open a new terminal and run:

```bash
ffmpeg -version
ffprobe -version
```

If the app cannot read the duration of a video, try a different `.mp4`, `.mov`, or `.m4v` file and confirm FFprobe is installed correctly.

If a generated output is missing or empty, try a short test video first and check the terminal window for detailed FFmpeg output.

If macOS refuses to open a `.command` file, run:

```bash
chmod +x setup_mac.command launch_app.command
```

## Local Files

The app creates local runtime folders in the project directory:

- `uploads/`
- `output/`
- `temp/`
- `venv/`

The app also creates a persistent Clip Library:

- `clip_library/intros/`
- `clip_library/outros/`
- `clip_library/promos/`
- `clip_library/clip_library.json`

Use **Upload and save to library** to give a clip a friendly name and optionally make it the default for its type. Defaults are preselected the next time the page opens, but you can always choose **None**. Use **Manage Clip Library** to set/remove defaults or delete clips.

The app copies saved videos into `clip_library` instead of linking arbitrary local browser paths. That makes saved selections reliable after browser restarts or moving the original file. Back up the entire `clip_library` folder (including `clip_library.json`) to preserve your saved clips and their names/defaults.

These are ignored by Git.
