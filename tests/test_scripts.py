"""Tests for the two capture scripts.

    python -m unittest discover tests

No network: link-ingest's parsing and caption handling are tested directly, and yt-dlp is
never called. media-ingest's end-to-end test needs ffmpeg; it makes a 3-second silent test
video, so Whisper is not needed either. Without ffmpeg it skips (CI installs ffmpeg).
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "skills", "reel-to-idea", "scripts")


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


link = load("link-ingest")
media = load("media-ingest")


class LinkIngest(unittest.TestCase):

    def test_comments_are_dropped_but_url_fragments_are_kept(self):
        text = ("# a comment line\n"
                "https://youtu.be/abc#t=30\n"
                "https://www.youtube.com/watch?v=x   # why I saved it\n"
                "\n"
                "not a url\n")
        self.assertEqual(link.parse_links(text),
                         ["https://youtu.be/abc#t=30", "https://www.youtube.com/watch?v=x"])

    def test_slug_cannot_become_a_path(self):
        for bad in ("../../etc/passwd", "a/b\\c", "..", "", "   "):
            s = link.slugify(bad)
            self.assertNotIn("/", s)
            self.assertNotIn("\\", s)
            self.assertNotIn("..", s)
            self.assertTrue(s)

    def test_platforms(self):
        self.assertEqual(link.platform_of("https://youtu.be/x"), "youtube")
        self.assertEqual(link.platform_of("https://www.instagram.com/reel/x"), "instagram")
        self.assertEqual(link.platform_of("https://example.com/v.mp4"), "other")

    def test_captions_become_the_same_transcript_shape_without_scroll_repeats(self):
        vtt = ("WEBVTT\nKind: captions\nLanguage: en\n\n"
               "1\n00:00:01.000 --> 00:00:03.000\nhello <c>there</c>\n\n"
               "2\n00:00:02.000 --> 00:00:04.000\nhello there\n\n"
               "3\n00:01:05.000 --> 00:01:07.000\nsecond line\n")
        md, n = link.vtt_to_markdown(vtt, "Title", "https://youtu.be/x", 67.0)
        self.assertEqual(n, 2)
        self.assertIn("**[00:01]** hello there", md)
        self.assertIn("**[01:05]** second line", md)
        self.assertIn("## Transcript", md)

    def test_failures_are_classified_not_retried(self):
        self.assertEqual(link.classify_failure("ERROR: Sign in to confirm you're not a bot"), "needs_screen_recording")
        self.assertEqual(link.classify_failure("HTTP Error 429: Too Many Requests"), "needs_screen_recording")
        self.assertEqual(link.classify_failure("ERROR: No video formats found"), "image_post")
        self.assertEqual(link.classify_failure("something else"), "failed")

    def test_refuses_to_overwrite_a_previous_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "manifest.json"), "w") as fh:
                fh.write("[]")
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "link-ingest.py"),
                                "--url", "https://youtu.be/x", "--out", d],
                               capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            if "yt-dlp not installed" not in p.stderr:
                self.assertIn("refusing to overwrite", p.stderr)
            with open(os.path.join(d, "manifest.json")) as fh:
                self.assertEqual(fh.read(), "[]")


class MediaIngest(unittest.TestCase):

    def test_frames_skip_the_first_and_last_moment(self):
        times = media.frame_times(10.0, 4)
        self.assertEqual(len(times), 4)
        self.assertTrue(all(0 < t < 10 for t in times))
        self.assertAlmostEqual(times[0], 2.0)

    def test_missing_file_is_a_clear_error(self):
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "media-ingest.py"), "no-such-video.mp4"],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("not a file", p.stderr)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
    def test_silent_video_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            video = os.path.join(d, "demo.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
                            "-pix_fmt", "yuv420p", video], check=True)
            out = os.path.join(d, "out")
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "media-ingest.py"), video,
                                "--out", out, "--frames", "3"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            res = os.path.join(out, "demo")
            self.assertEqual(len(os.listdir(os.path.join(res, "frames"))), 3)
            with open(os.path.join(res, "transcript.md"), encoding="utf-8") as fh:
                self.assertIn("No speech detected", fh.read())
            with open(os.path.join(res, "meta.json"), encoding="utf-8") as fh:
                meta = json.load(fh)
            self.assertFalse(meta["has_audio"])
            self.assertAlmostEqual(meta["duration"], 3.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
