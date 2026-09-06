import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from rd_cliprip.services import downloader
from rd_cliprip.services.downloader import (
    OUTPUT_TEMPLATE,
    describe_failure,
    is_fatal_error,
)


class BuildArgsTests(unittest.TestCase):
    """Lock the exact yt-dlp command line ClipRip produces."""

    def _args(self, **overrides):
        defaults = dict(
            url="https://example.com/v",
            output_dir=r"C:\dl",
            preferred_format="mp4",
            preferred_resolution="1080p",
            embed_subs=False,
        )
        defaults.update(overrides)
        with patch.object(downloader, "find_ytdlp_exe", return_value="yt-dlp.exe"):
            return downloader.build_ytdlp_args(**defaults)

    def _fmt(self, **overrides):
        args = self._args(**overrides)
        return args[args.index("-f") + 1]

    def test_mp4_prefers_h264_first(self):
        fmt = self._fmt()
        self.assertTrue(fmt.startswith("best[ext=mp4][vcodec=h264][height<=1080]"), fmt)
        self.assertIn("vcodec!=av1", fmt)
        self.assertTrue(fmt.endswith("/best"))

    def test_mp4_resolution_cap(self):
        self.assertIn("[height<=720]", self._fmt(preferred_resolution="720p"))

    def test_mp4_avoids_av1(self):
        self.assertIn("[vcodec!=av1]", self._fmt())

    def test_no_remux_by_default(self):
        self.assertNotIn("--remux-video", self._args())

    def test_remux_applied_when_enabled(self):
        args = self._args(remux_to_mp4=True)
        self.assertEqual(args[args.index("--remux-video") + 1], "mp4")

    def test_mkv_merges(self):
        args = self._args(preferred_format="mkv")
        self.assertEqual(args[args.index("--merge-output-format") + 1], "mkv")

    def test_no_playlist_flag(self):
        self.assertIn("--no-playlist", self._args())
        self.assertNotIn("--no-playlist", self._args(no_playlist=False))

    def test_rate_limit_flag(self):
        args = self._args(rate_limit_mbps=2.5)
        self.assertEqual(args[args.index("--limit-rate") + 1], "2.50M")

    def test_concurrent_fragments_flag(self):
        args = self._args(concurrent_fragments=8)
        self.assertEqual(args[args.index("--concurrent-fragments") + 1], "8")
        self.assertNotIn("--concurrent-fragments", self._args(concurrent_fragments=0))
        self.assertNotIn("--concurrent-fragments", self._args(concurrent_fragments=1))

    def test_ffmpeg_location_flag(self):
        args = self._args(ffmpeg_location=r"C:\tools")
        self.assertEqual(args[args.index("--ffmpeg-location") + 1], r"C:\tools")

    def test_output_template_truncates_title(self):
        # Keep staging paths short enough for Windows' ~260 char limit.
        self.assertIn("%(title).140s", OUTPUT_TEMPLATE)
        self.assertIn("[%(id)s]", OUTPUT_TEMPLATE)

    def test_describe_failure_not_found(self):
        self.assertEqual(describe_failure("ERROR: unable to extract hash from URL"), "Not found")
        self.assertEqual(describe_failure("404: video not found"), "Not found")
        self.assertNotEqual(describe_failure("HTTP Error 500"), "Not found")
        self.assertEqual(describe_failure(""), "Failed")

    def test_unable_to_extract_is_fatal(self):
        self.assertTrue(is_fatal_error("ERROR: unable to extract anything"))


if __name__ == "__main__":
    unittest.main()
