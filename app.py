import os
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
CLIP_LIBRARY_DIR = BASE_DIR / "clip_library"
CLIP_LIBRARY_FILE = CLIP_LIBRARY_DIR / "clip_library.json"
CLIP_TYPES = {"intro", "outro", "promo"}
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
PROCESSING_JOBS = {}
PROCESSING_JOBS_LOCK = threading.Lock()


class ClipSplicerError(Exception):
    """User-facing error that can be safely shown in the browser."""


def get_ffmpeg_install_help():
    system_name = platform.system()
    if system_name == "Darwin":
        return "Install FFmpeg with Homebrew: brew install ffmpeg"
    if system_name == "Windows":
        return "Install FFmpeg with winget: winget install --id Gyan.FFmpeg -e"
    return "Install FFmpeg for your operating system and make sure ffmpeg and ffprobe are on PATH."


def missing_tool_message(name):
    return (
        f"{name} is not installed or could not be found on PATH. "
        f"{get_ffmpeg_install_help()}"
    )


def ensure_directories():
    for folder in (UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, CLIP_LIBRARY_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    for clip_type in CLIP_TYPES:
        (CLIP_LIBRARY_DIR / f"{clip_type}s").mkdir(parents=True, exist_ok=True)


def clip_library_folder(clip_type):
    if clip_type not in CLIP_TYPES:
        raise ClipSplicerError("Please choose a valid clip type.")
    return CLIP_LIBRARY_DIR / f"{clip_type}s"


def empty_clip_library():
    return {"clips": []}


def load_clip_library():
    ensure_directories()
    if not CLIP_LIBRARY_FILE.exists():
        return empty_clip_library()
    try:
        content = CLIP_LIBRARY_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(content) if content else empty_clip_library()
        if not isinstance(data, dict) or not isinstance(data.get("clips", []), list):
            raise ValueError("Invalid clip library structure")
        return {"clips": [clip for clip in data["clips"] if isinstance(clip, dict)]}
    except (OSError, json.JSONDecodeError, ValueError):
        print("Clip library metadata was missing or malformed; starting with an empty library.")
        return empty_clip_library()


def save_clip_library(library):
    ensure_directories()
    temp_path = CLIP_LIBRARY_FILE.with_suffix(".json.tmp")
    try:
        temp_path.write_text(json.dumps(library, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, CLIP_LIBRARY_FILE)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise ClipSplicerError("Could not save the Clip Library. Please try again.") from exc


def clips_for_template():
    clips = load_clip_library()["clips"]
    grouped = {clip_type: [] for clip_type in CLIP_TYPES}
    for clip in clips:
        if clip.get("type") in grouped:
            clip = dict(clip)
            clip["available"] = library_clip_path(clip).is_file()
            grouped[clip["type"]].append(clip)
    for clip_type in grouped:
        grouped[clip_type].sort(key=lambda clip: clip.get("created_at", ""), reverse=True)
    return grouped


def library_clip_path(clip):
    filename = Path(str(clip.get("filename", ""))).name
    return clip_library_folder(clip.get("type")) / filename


def get_library_clip(clip_id, expected_type):
    for clip in load_clip_library()["clips"]:
        if clip.get("id") == clip_id and clip.get("type") == expected_type:
            path = library_clip_path(clip)
            if not path.is_file():
                raise ClipSplicerError(f'The saved {expected_type} clip "{clip.get("name", "clip")}" is missing.')
            return path
    raise ClipSplicerError(f"The selected saved {expected_type} clip could not be found.")


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
        raise ClipSplicerError(missing_tool_message(name))
    return tool_path


def require_tool(name):
    return resolve_tool(name)


def require_ffmpeg_tools():
    require_tool("ffmpeg")
    require_tool("ffprobe")


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
        raise ClipSplicerError(missing_tool_message(command_args[0])) from exc
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
            f"FFprobe could not read the video duration. {get_ffmpeg_install_help()}"
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
            escaped_path = Path(video_path).resolve().as_posix().replace("'", "'\\''")
            file.write(f"file '{escaped_path}'\n")


def concat_videos(video_paths, output_path):
    concat_fd, concat_list_name = tempfile.mkstemp(
        prefix="concat_",
        suffix=".txt",
        dir=TEMP_DIR,
    )
    os.close(concat_fd)
    concat_list = Path(concat_list_name)
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
    try:
        get_video_duration_seconds(destination)
        return destination
    except ClipSplicerError:
        destination.unlink(missing_ok=True)
        raise


def save_library_upload(file_storage, clip_type, name, make_default=False):
    if not file_storage or not file_storage.filename:
        raise ClipSplicerError(f"Please choose a {clip_type} file to save.")
    safe_name = secure_filename(file_storage.filename)
    if not safe_name or not allowed_file(safe_name):
        raise ClipSplicerError("Please upload a valid video file: .mp4, .mov, or .m4v.")
    display_name = (name or "").strip()
    if not display_name:
        raise ClipSplicerError("Please enter a friendly clip name.")

    clip_id = str(uuid4())
    destination = clip_library_folder(clip_type) / f"{clip_id}_{safe_name}"
    file_storage.save(destination)
    try:
        duration = get_video_duration_seconds(destination)
    except ClipSplicerError:
        destination.unlink(missing_ok=True)
        raise

    library = load_clip_library()
    if make_default:
        for clip in library["clips"]:
            if clip.get("type") == clip_type:
                clip["is_default"] = False
    library["clips"].append(
        {
            "id": clip_id,
            "name": display_name,
            "type": clip_type,
            "filename": destination.name,
            "original_filename": file_storage.filename,
            "duration_seconds": round(duration, 2),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "is_default": bool(make_default),
        }
    )
    try:
        save_clip_library(library)
    except ClipSplicerError:
        destination.unlink(missing_ok=True)
        raise
    return destination


def resolve_clip_source(clip_type, mode, file_storage, library_id, name, make_default):
    mode = mode or "none"
    if mode == "none":
        return None
    if mode == "library":
        if not library_id:
            raise ClipSplicerError(f"Please select a saved {clip_type} clip.")
        return get_library_clip(library_id, clip_type)
    if mode == "upload":
        return save_upload(file_storage, f"{clip_type}_one_time")
    if mode == "save":
        return save_library_upload(file_storage, clip_type, name, make_default)
    raise ClipSplicerError(f"Please choose a valid {clip_type} option.")


def process_video(main_path, intro_path=None, promo_path=None, placement="none", timestamp_string="", outro_path=None, progress_callback=None):
    require_ffmpeg_tools()
    selected_paths = [path for path in (main_path, intro_path, promo_path, outro_path) if path]
    total_steps = len(selected_paths) + 1
    completed_steps = 0

    def update_progress(message):
        nonlocal completed_steps
        completed_steps += 1
        if progress_callback:
            progress_callback(message, min(95, int(completed_steps / total_steps * 85) + 10))

    with tempfile.TemporaryDirectory(dir=TEMP_DIR) as working_dir_name:
        working_dir = Path(working_dir_name)
        normalized_main = working_dir / "main_normalized.mp4"
        normalize_video(main_path, normalized_main)
        update_progress("Normalized main video")
        normalized_intro = None
        normalized_outro = None
        normalized_promo = None
        if intro_path:
            normalized_intro = working_dir / "intro_normalized.mp4"
            normalize_video(intro_path, normalized_intro)
            update_progress("Normalized intro")
        if outro_path:
            normalized_outro = working_dir / "outro_normalized.mp4"
            normalize_video(outro_path, normalized_outro)
            update_progress("Normalized outro")
        if promo_path:
            normalized_promo = working_dir / "promo_normalized.mp4"
            normalize_video(promo_path, normalized_promo)
            update_progress("Normalized promo clip")

        if not normalized_promo or placement == "none":
            sequence = [normalized_main]
        elif placement == "beginning":
            sequence = [normalized_promo, normalized_main]
        elif placement == "end":
            sequence = [normalized_main, normalized_promo]
        elif placement == "custom":
            main_duration = get_video_duration_seconds(main_path)
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

        if normalized_intro:
            sequence.insert(0, normalized_intro)
        if normalized_outro:
            sequence.append(normalized_outro)

        output_name = f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = OUTPUT_DIR / output_name
        if progress_callback:
            progress_callback("Combining video segments", 95)
        concat_videos(sequence, output_path)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ClipSplicerError(
            "The video was processed, but the output file appears to be empty. Please try again."
        )

    return output_name


def update_job(job_id, **values):
    with PROCESSING_JOBS_LOCK:
        if job_id in PROCESSING_JOBS:
            PROCESSING_JOBS[job_id].update(values)


def run_processing_job(job_id, main_path, intro_path, promo_path, placement, timestamp, outro_path):
    try:
        output_filename = process_video(
            main_path, intro_path, promo_path, placement, timestamp, outro_path,
            progress_callback=lambda message, progress: update_job(
                job_id, state="processing", message=message, progress=progress
            ),
        )
        update_job(job_id, state="complete", message="Your video is ready.", progress=100, output_filename=output_filename)
    except ClipSplicerError as exc:
        update_job(job_id, state="error", message=str(exc), progress=0)
    except Exception as exc:
        print("Unexpected error while processing video:")
        print(exc)
        update_job(job_id, state="error", message="Something went wrong while processing the video.", progress=0)


@app.route("/")
def index():
    return render_template("index.html", clips_by_type=clips_for_template())


def render_index(**kwargs):
    return render_template("index.html", clips_by_type=clips_for_template(), **kwargs)


@app.route("/process", methods=["POST"])
def process():
    try:
        main_path = save_upload(request.files.get("main_video"), "main_video")
        intro_path = resolve_clip_source(
            "intro", request.form.get("intro_mode"), request.files.get("intro_file"),
            request.form.get("intro_library_id"), request.form.get("intro_name"),
            request.form.get("intro_default") == "on",
        )
        promo_path = resolve_clip_source(
            "promo", request.form.get("promo_mode"), request.files.get("promo_file"),
            request.form.get("promo_library_id"), request.form.get("promo_name"),
            request.form.get("promo_default") == "on",
        )
        outro_path = resolve_clip_source(
            "outro", request.form.get("outro_mode"), request.files.get("outro_file"),
            request.form.get("outro_library_id"), request.form.get("outro_name"),
            request.form.get("outro_default") == "on",
        )
        placement = request.form.get("placement", "none") if promo_path else "none"
        output_filename = process_video(
            main_path,
            intro_path,
            promo_path,
            placement,
            request.form.get("timestamp", ""),
            outro_path,
        )
        return render_index(
            success_message="Your video is ready.",
            download_filename=output_filename,
        )
    except ClipSplicerError as exc:
        return render_index(error_message=str(exc)), 400
    except Exception as exc:
        print("Unexpected error while processing video:")
        print(exc)
        return render_index(
            error_message="Something went wrong while processing the video. Please try again.",
        ), 500


@app.route("/start-process", methods=["POST"])
def start_process():
    try:
        main_path = save_upload(request.files.get("main_video"), "main_video")
        intro_path = resolve_clip_source(
            "intro", request.form.get("intro_mode"), request.files.get("intro_file"),
            request.form.get("intro_library_id"), request.form.get("intro_name"),
            request.form.get("intro_default") == "on",
        )
        promo_path = resolve_clip_source(
            "promo", request.form.get("promo_mode"), request.files.get("promo_file"),
            request.form.get("promo_library_id"), request.form.get("promo_name"),
            request.form.get("promo_default") == "on",
            )
        outro_path = resolve_clip_source(
            "outro", request.form.get("outro_mode"), request.files.get("outro_file"),
            request.form.get("outro_library_id"), request.form.get("outro_name"),
            request.form.get("outro_default") == "on",
        )
        placement = request.form.get("placement", "none") if promo_path else "none"
        job_id = str(uuid4())
        with PROCESSING_JOBS_LOCK:
            PROCESSING_JOBS[job_id] = {
                "state": "processing",
                "message": "Preparing video files",
                "progress": 5,
            }
        worker = threading.Thread(
            target=run_processing_job,
            args=(job_id, main_path, intro_path, promo_path, placement, request.form.get("timestamp", ""), outro_path),
            daemon=True,
        )
        worker.start()
        return jsonify({"job_id": job_id}), 202
    except ClipSplicerError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/process-status/<job_id>")
def process_status(job_id):
    with PROCESSING_JOBS_LOCK:
        job = PROCESSING_JOBS.get(job_id)
        if not job:
            return jsonify({"error": "That processing job could not be found."}), 404
        response = dict(job)
    if response.get("output_filename"):
        response["download_url"] = request.url_root.rstrip("/") + app.url_for("download", filename=response["output_filename"])
    return jsonify(response)


@app.route("/library/default", methods=["POST"])
def set_library_default():
    try:
        clip_id = request.form.get("clip_id", "")
        library = load_clip_library()
        selected = next((clip for clip in library["clips"] if clip.get("id") == clip_id), None)
        if not selected:
            raise ClipSplicerError("That saved clip could not be found.")
        make_default = request.form.get("make_default") == "true"
        for clip in library["clips"]:
            if clip.get("type") == selected["type"]:
                clip["is_default"] = make_default and clip.get("id") == clip_id
        save_clip_library(library)
        return render_index(success_message="Clip Library default updated.")
    except ClipSplicerError as exc:
        return render_index(error_message=str(exc)), 400


@app.route("/library/delete", methods=["POST"])
def delete_library_clip():
    try:
        clip_id = request.form.get("clip_id", "")
        library = load_clip_library()
        clip = next((item for item in library["clips"] if item.get("id") == clip_id), None)
        if not clip:
            raise ClipSplicerError("That saved clip could not be found.")
        path = library_clip_path(clip)
        if CLIP_LIBRARY_DIR not in path.resolve().parents:
            raise ClipSplicerError("Invalid clip library file.")
        path.unlink(missing_ok=True)
        library["clips"] = [item for item in library["clips"] if item.get("id") != clip_id]
        save_clip_library(library)
        return render_index(success_message="Saved clip deleted.")
    except ClipSplicerError as exc:
        return render_index(error_message=str(exc)), 400


@app.route("/download/<path:filename>")
def download(filename):
    safe_filename = secure_filename(filename)
    output_path = OUTPUT_DIR / safe_filename
    if safe_filename != filename or not output_path.exists():
        return render_template("index.html", error_message="That output file could not be found."), 404
    return send_from_directory(OUTPUT_DIR, safe_filename, as_attachment=True)


if __name__ == "__main__":
    try:
        require_ffmpeg_tools()
    except ClipSplicerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    ensure_directories()
    print("Open this address in your browser: http://127.0.0.1:5050", flush=True)
    app.run(host="127.0.0.1", port=5050, debug=False)
