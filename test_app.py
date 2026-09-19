import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as clip_app


class ClipSplicerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.paths = {
            "UPLOAD_DIR": base / "uploads",
            "OUTPUT_DIR": base / "output",
            "TEMP_DIR": base / "temp",
            "CLIP_LIBRARY_DIR": base / "clip_library",
            "CLIP_LIBRARY_FILE": base / "clip_library" / "clip_library.json",
        }
        self.patcher = patch.multiple(clip_app, **self.paths)
        self.patcher.start()
        clip_app.ensure_directories()
        clip_app.app.config.update(TESTING=True)
        self.client = clip_app.app.test_client()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    @patch.object(clip_app, "get_video_duration_seconds", return_value=8.4)
    def test_saving_clip_uses_unique_filename_and_persists(self, _duration):
        first = clip_app.save_library_upload(self.upload("intro.mp4"), "intro", "First")
        second = clip_app.save_library_upload(self.upload("intro.mp4"), "intro", "Second")
        self.assertNotEqual(first.name, second.name)
        library = clip_app.load_clip_library()
        self.assertEqual(2, len(library["clips"]))
        self.assertEqual("intro.mp4", library["clips"][0]["original_filename"])

    @patch.object(clip_app, "get_video_duration_seconds", return_value=8.4)
    def test_defaults_are_unique_and_survive_reload(self, _duration):
        clip_app.save_library_upload(self.upload("a.mp4"), "promo", "A", True)
        clip_app.save_library_upload(self.upload("b.mp4"), "promo", "B", True)
        reloaded = clip_app.load_clip_library()["clips"]
        self.assertEqual(1, sum(clip["is_default"] for clip in reloaded))

    def test_malformed_library_recovers_empty(self):
        clip_app.CLIP_LIBRARY_FILE.write_text("not json", encoding="utf-8")
        self.assertEqual([], clip_app.load_clip_library()["clips"])

    def test_invalid_file_type_is_rejected(self):
        with self.assertRaises(clip_app.ClipSplicerError):
            clip_app.save_library_upload(self.upload("not-video.txt"), "intro", "Nope")

    def test_delete_rejects_unknown_or_traversal_id(self):
        response = self.client.post("/library/delete", data={"clip_id": "../../outside"})
        self.assertEqual(400, response.status_code)

    @patch.object(clip_app, "concat_videos")
    @patch.object(clip_app, "normalize_video")
    @patch.object(clip_app, "require_ffmpeg_tools")
    def test_segment_orders(self, _tools, _normalize, concat):
        for name in ("main.mp4", "intro.mp4", "promo.mp4", "outro.mp4"):
            (clip_app.UPLOAD_DIR / name).write_bytes(b"x")
        concat.side_effect = lambda _videos, output: output.write_bytes(b"output")
        with patch.object(clip_app, "get_video_duration_seconds", return_value=10):
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4")
            self.assertEqual(["main_normalized.mp4"], [path.name for path in concat.call_args.args[0]])
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", clip_app.UPLOAD_DIR / "intro.mp4")
            self.assertEqual(["intro_normalized.mp4", "main_normalized.mp4"], [path.name for path in concat.call_args.args[0]])
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", None, None, "none", "", clip_app.UPLOAD_DIR / "outro.mp4")
            self.assertEqual(["main_normalized.mp4", "outro_normalized.mp4"], [path.name for path in concat.call_args.args[0]])
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", clip_app.UPLOAD_DIR / "intro.mp4", None, "none", "", clip_app.UPLOAD_DIR / "outro.mp4")
            self.assertEqual(["intro_normalized.mp4", "main_normalized.mp4", "outro_normalized.mp4"], [path.name for path in concat.call_args.args[0]])
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", clip_app.UPLOAD_DIR / "intro.mp4", clip_app.UPLOAD_DIR / "promo.mp4", "beginning", "", clip_app.UPLOAD_DIR / "outro.mp4")
            sequence = [path.name for path in concat.call_args.args[0]]
            self.assertEqual(["intro_normalized.mp4", "promo_normalized.mp4", "main_normalized.mp4", "outro_normalized.mp4"], sequence)
            clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", None, clip_app.UPLOAD_DIR / "promo.mp4", "end", "", clip_app.UPLOAD_DIR / "outro.mp4")
            self.assertEqual(["main_normalized.mp4", "promo_normalized.mp4", "outro_normalized.mp4"], [path.name for path in concat.call_args.args[0]])

    @patch.object(clip_app, "concat_videos")
    @patch.object(clip_app, "split_video")
    @patch.object(clip_app, "normalize_video")
    @patch.object(clip_app, "require_ffmpeg_tools")
    @patch.object(clip_app, "get_video_duration_seconds", return_value=10)
    def test_custom_promo_order(self, _duration, _tools, _normalize, split, concat):
        for name in ("main.mp4", "promo.mp4", "outro.mp4"):
            (clip_app.UPLOAD_DIR / name).write_bytes(b"x")
        concat.side_effect = lambda _videos, output: output.write_bytes(b"output")
        clip_app.process_video(clip_app.UPLOAD_DIR / "main.mp4", None, clip_app.UPLOAD_DIR / "promo.mp4", "custom", "5", clip_app.UPLOAD_DIR / "outro.mp4")
        self.assertEqual(["main_part_1.mp4", "promo_normalized.mp4", "main_part_2.mp4", "outro_normalized.mp4"], [path.name for path in concat.call_args.args[0]])

    @staticmethod
    def upload(name):
        from werkzeug.datastructures import FileStorage
        return FileStorage(stream=io.BytesIO(b"video"), filename=name, content_type="video/mp4")


if __name__ == "__main__":
    unittest.main()
