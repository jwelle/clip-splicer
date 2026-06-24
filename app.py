import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v"}
COMMON_TOOL_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
]

os.environ["PATH"] = os.pathsep.join(
    COMMON_TOOL_PATHS + [os.environ.get("PATH", "")]
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024


class ClipSplicerError(Exception):
    """User-facing error that can be safely shown in the browser."""


def ensure_directories():
    for folder in (UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def parse_timestamp_to_seconds(timestamp_string):
    value = (timestamp_string or "").strip()
    if not value:
        raise ClipSplicerError("Please enter a timestamp.")

    parts = value.split(":")
    if len(parts) > 3:
        raise ClipSplicerError("Please enter a valid timestamp.")

    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        else:
            if any(part == "" or not part.isdigit() for part in parts):
                raise ValueError
            numbers = [int(part) for part in parts]
            if numbers[-1] >= 60 or (len(numbers) == 3 and numbers[-2] >= 60):
                raise ValueError
            if len(numbers) == 2:
                seconds = numbers[0] * 60 + numbers[1]
            else:
                seconds = numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    except ValueError as exc:
        raise ClipSplicerError("Please enter a valid timestamp.") from exc

    if seconds < 0:
        raise ClipSplicerError("Timestamp must be greater than or equal to 0.")

    return seconds


def resolve_tool(name):
    tool_path = shutil.which(name)
    if not tool_path:
        raise ClipSplicerError(
            f"{name} is not installed or could not be found. Please confirm FFmpeg is installed correctly."
        )
    return tool_path


def require_tool(name):
    return resolve_tool(name)


def run_ffmpeg_command(command_args, friendly_error):
    try:
        subprocess.run(
            command_args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        print(f"Missing command: {command_args[0]}")
        raise ClipSplicerError(
            "FFmpeg is not installed or could not be found. Please confirm FFmpeg is installed correctly."
        ) from exc
    except subprocess.CalledProcessError as exc:
        print("Command failed:")
        print(" ".join(command_args))
        print(exc.stderr)
        raise ClipSplicerError(friendly_error) from exc


def get_video_duration_seconds(video_path):
    ffprobe = require_tool("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        print("FFprobe duration detection failed.")
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr)
        raise ClipSplicerError(
            "FFprobe could not read the video duration. Please confirm FFmpeg is installed correctly."
        ) from exc


def video_has_audio_stream(video_path):
    ffprobe = require_tool("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def normalize_video(input_path, output_path):
    ffmpeg = require_tool("ffmpeg")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
    ]

    if video_has_audio_stream(input_path):
        command.extend(["-map", "0:v:0", "-map", "0:a:0"])
    else:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
            ]
        )

    command.extend(
        [
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
        ]
    )
    run_ffmpeg_command(command, "FFmpeg could not normalize one of the videos.")


def split_video(input_path, start_time, duration_or_end, output_path):
    ffmpeg = require_tool("ffmpeg")
    command = [ffmpeg, "-y", "-ss", str(start_time), "-i", str(input_path)]
    if duration_or_end is not None:
        command.extend(["-t", str(duration_or_end)])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    run_ffmpeg_command(command, "FFmpeg could not split the main video.")


def write_concat_list(video_paths, list_path):
    with list_path.open("w", encoding="utf-8") as file:
        for video_path in video_paths:
            escaped_path = str(Path(video_path).resolve()).replace("'", "'\\''")
            file.write(f"file '{escaped_path}'\n")


def concat_videos(video_paths, output_path):
    concat_list = Path(tempfile.mkstemp(prefix="concat_", suffix=".txt", dir=TEMP_DIR)[1])
    write_concat_list(video_paths, concat_list)
    ffmpeg = require_tool("ffmpeg")

    copy_command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        str(output_path),
    ]

    try:
        run_ffmpeg_command(copy_command, "FFmpeg concat stream copy failed.")
    except ClipSplicerError:
        reencode_command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        run_ffmpeg_command(reencode_command, "FFmpeg could not concatenate the videos.")
    finally:
        concat_list.unlink(missing_ok=True)


def save_upload(file_storage, prefix):
    if not file_storage or not file_storage.filename:
        raise ClipSplicerError(f"Please choose a {prefix.replace('_', ' ')} file.")

    filename = secure_filename(file_storage.filename)
    if not filename or not allowed_file(filename):
        raise ClipSplicerError("Please upload a valid video file: .mp4, .mov, or .m4v.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = UPLOAD_DIR / f"{prefix}_{timestamp}_{filename}"
    file_storage.save(destination)
    return destination


def process_video(main_path, promo_path, placement, timestamp_string):
    require_tool("ffmpeg")
    require_tool("ffprobe")

    main_duration = get_video_duration_seconds(main_path)
    with tempfile.TemporaryDirectory(dir=TEMP_DIR) as working_dir_name:
        working_dir = Path(working_dir_name)
        normalized_main = working_dir / "main_normalized.mp4"
        normalized_promo = working_dir / "promo_normalized.mp4"
        normalize_video(main_path, normalized_main)
        normalize_video(promo_path, normalized_promo)

        if placement == "beginning":
            sequence = [normalized_promo, normalized_main]
        elif placement == "end":
            sequence = [normalized_main, normalized_promo]
        elif placement == "custom":
            timestamp_seconds = parse_timestamp_to_seconds(timestamp_string)
            if timestamp_seconds > main_duration:
                raise ClipSplicerError("The selected timestamp is longer than the video duration.")
            if abs(timestamp_seconds) < 0.001:
                sequence = [normalized_promo, normalized_main]
            elif abs(timestamp_seconds - main_duration) < 0.001:
                sequence = [normalized_main, normalized_promo]
            else:
                first_part = working_dir / "main_part_1.mp4"
                second_part = working_dir / "main_part_2.mp4"
                split_video(normalized_main, 0, timestamp_seconds, first_part)
                split_video(normalized_main, timestamp_seconds, None, second_part)
                sequence = [first_part, normalized_promo, second_part]
        else:
            raise ClipSplicerError("Please choose where to place the promo clip.")

        output_name = f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = OUTPUT_DIR / output_name
        concat_videos(sequence, output_path)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ClipSplicerError(
            "The video was processed, but the output file appears to be empty. Please try again."
        )

    return output_name


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    try:
        main_path = save_upload(request.files.get("main_video"), "main_video")
        promo_path = save_upload(request.files.get("promo_clip"), "promo_clip")
        placement = request.form.get("placement", "beginning")
        output_filename = process_video(
            main_path,
            promo_path,
            placement,
            request.form.get("timestamp", ""),
        )
        return render_template(
            "index.html",
            success_message="Your video is ready.",
            download_filename=output_filename,
        )
    except ClipSplicerError as exc:
        return render_template("index.html", error_message=str(exc)), 400
    except Exception as exc:
        print("Unexpected error while processing video:")
        print(exc)
        return render_template(
            "index.html",
            error_message="Something went wrong while processing the video. Please try again.",
        ), 500


@app.route("/download/<path:filename>")
def download(filename):
    safe_filename = secure_filename(filename)
    output_path = OUTPUT_DIR / safe_filename
    if safe_filename != filename or not output_path.exists():
        return render_template("index.html", error_message="That output file could not be found."), 404
    return send_from_directory(OUTPUT_DIR, safe_filename, as_attachment=True)


if __name__ == "__main__":
    ensure_directories()
    print("Open this address in your browser: http://127.0.0.1:5050", flush=True)
    app.run(host="127.0.0.1", port=5050, debug=False)
