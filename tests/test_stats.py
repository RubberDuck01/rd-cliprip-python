import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from rd_cliprip.models.stats import Stats


class StatsResetTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp(prefix="cliprip_stats_")
        os.environ["LOCALAPPDATA"] = d
        os.environ["APPDATA"] = d

    def test_reset_zeroes_counters(self):
        stats = Stats()
        stats.add_successful_download(size_mb=10.0, duration_sec=120, file_count=2)
        self.assertEqual(stats.data["total_files_downloaded"], 2)

        stats.reset()
        reloaded = Stats()
        self.assertEqual(reloaded.data["total_files_downloaded"], 0)
        self.assertEqual(reloaded.data["total_downloads_size"], 0.0)
        self.assertEqual(reloaded.data["total_downloads_duration"], 0)
        self.assertEqual(reloaded.data["total_downloads_size_pretty"], "0.00 B")


if __name__ == "__main__":
    unittest.main()
