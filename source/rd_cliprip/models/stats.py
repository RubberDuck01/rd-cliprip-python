import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

class Stats:
    def __init__(self) -> None:
        # Win/Linux paths:
        if os.name == "nt":
            base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        else:
            base = Path.home() / ".config"

        self.data_dir = base / "Rubber Duck Softworks" / "ClipRip" / "Data"
        self.data_file = self.data_dir / "stats.json"
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.data_file.exists():
            try:
                self.data = json.loads(self.data_file.read_text(encoding="utf-8"))
            except Exception:
                self.data = self.default_stats()
        else:
            self.data = self.default_stats()
            self.save()

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data["total_downloads_duration_pretty"] = self.format_duration(
            int(self.data.get("total_downloads_duration", 0.0))
        )
        self.data["total_downloads_size_pretty"] = self.format_size(
            float(self.data.get("total_downloads_size", 0.0))
        )
        self.data_file.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def default_stats(self) -> dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "created_date": now,
            "last_run_date": now,
            "total_sessions": 0,
            "total_files_downloaded": 0,
            "total_downloads_size": 0.0,  # MB
            "total_downloads_duration": 0,  # seconds
            "total_downloads_duration_pretty": "00:00",
            "total_downloads_size_pretty": "0 B",
        }

    def register_session(self) -> None:
        self.data["last_run_date"] = datetime.now().isoformat()
        self.data["total_sessions"] = int(self.data.get("total_sessions", 0)) + 1
        self.save()

    def add_successful_download(
        self, size_mb: float, duration_sec: int, file_count: int = 1
    ) -> None:
        self.data["total_files_downloaded"] = (
            int(self.data.get("total_files_downloaded", 0)) + max(1, file_count)
        )
        self.data["total_downloads_size"] = (
            float(self.data.get("total_downloads_size", 0.0)) + max(0.0, size_mb)
        )
        self.data["total_downloads_duration"] = (
            int(self.data.get("total_downloads_duration", 0)) + max(0, duration_sec)
        )
        self.save()

    @staticmethod
    def format_duration(seconds: int) -> str:
        m, s = divmod(max(0, seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02}:{m:02}:{s:02}"
        return f"{m:02}:{s:02}"

    @staticmethod
    def format_size(size_mb: float) -> str:
        size_b = max(0.0, size_mb) * 1024 * 1024
        units = ["B", "KB", "MB", "GB", "TB"]
        value = size_b
        idx = 0

        while value >= 1024 and idx < len(units) - 1:
            value /= 1024
            idx += 1

        return f"{value:.2f} {units[idx]}"
