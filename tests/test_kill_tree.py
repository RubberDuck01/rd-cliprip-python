import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from rd_cliprip.controllers.download_manager import DownloadManager


class KillTreeTests(unittest.TestCase):
    def test_taskkill_suppresses_console_window(self):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.pid = 4321

        with patch(
            "rd_cliprip.controllers.download_manager.subprocess.run"
        ) as run:
            DownloadManager._kill_tree(proc)

        self.assertTrue(run.called, "taskkill was not invoked")
        command = run.call_args.args[0]
        self.assertIn("taskkill", command)
        if sys.platform == "win32":
            self.assertEqual(
                run.call_args.kwargs.get("creationflags"),
                subprocess.CREATE_NO_WINDOW,
            )


if __name__ == "__main__":
    unittest.main()
