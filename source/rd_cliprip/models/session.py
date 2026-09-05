import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# Item lifecycle states
STATE_QUEUED = "queued"
STATE_ACTIVE = "active"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"

# States that still have work to do on a resume.
RESUMABLE_STATES = (STATE_QUEUED, STATE_FAILED, STATE_CANCELLED)


@dataclass
class SessionItem:
    url: str
    title: str = ""
    state: str = STATE_QUEUED
    attempts: int = 0
    error: str = ""
    progress: int = 0
    playlist: bool = False
    dest_paths: list[str] = field(default_factory=list)
    size_mb: float = 0.0
    duration_sec: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionItem":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def _data_dir() -> Path:
    """Return the app data dir shared with Stats."""
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".config"
    return base / "Rubber Duck Softworks" / "ClipRip" / "Data"


class DownloadSession:
    """Persistent, resumable queue of URLs to download.

    A session is the source of truth for a batch of downloads.  It stores
    enough per-item state (status, retry attempts, final file paths) to
    resume after the app is stopped and restarted.
    """

    def __init__(self, output_dir: str, source_file: str = "") -> None:
        self.data_dir = _data_dir()
        self.session_file = self.data_dir / "session.json"
        self.history_dir = self.data_dir / "session_history"
        self.output_dir = output_dir
        self.source_file = source_file
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.items: list[SessionItem] = []

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        self.updated_at = datetime.now().isoformat()
        payload = {
            "version": 1,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "output_dir": self.output_dir,
            "source_file": self.source_file,
            "items": [i.to_dict() for i in self.items],
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls) -> "DownloadSession | None":
        session_file = _data_dir() / "session.json"
        if not session_file.exists():
            return None
        try:
            payload = json.loads(session_file.read_text(encoding="utf-8"))
        except Exception:
            return None

        session = cls(
            output_dir=str(payload.get("output_dir", "")),
            source_file=str(payload.get("source_file", "")),
        )
        session.created_at = str(payload.get("created_at", session.created_at))
        session.updated_at = str(payload.get("updated_at", session.updated_at))
        session.items = [SessionItem.from_dict(d) for d in payload.get("items", [])]
        return session

    def archive(self) -> None:
        """Move the active session file into history (e.g. before starting a new one).

        History is capped: only the most recent ``_MAX_HISTORY`` archives are kept.
        """
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.session_file.exists():
                self.session_file.rename(
                    self.history_dir / f"session_{stamp}.json"
                )
            self._prune_history()
        except Exception:
            pass

    def _prune_history(self, keep: int = 10) -> None:
        try:
            archives = sorted(self.history_dir.glob("session_*.json"))
            for old in archives[:-keep]:
                old.unlink()
        except Exception:
            pass

    def clear_file(self) -> None:
        try:
            if self.session_file.exists():
                self.session_file.unlink()
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  Items
    # ------------------------------------------------------------------

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def add_url(self, url: str) -> SessionItem:
        item = SessionItem(url=url.strip())
        self.items.append(item)
        self.touch()
        return item

    def add_urls(self, urls: list[str]) -> list[SessionItem]:
        added = [self.add_url(u) for u in urls]
        return added

    def get_item(self, item_id: str) -> SessionItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def next_queued(self) -> SessionItem | None:
        """Return the first item that still needs work, or None."""
        for item in self.items:
            if item.state in RESUMABLE_STATES:
                return item
        return None

    def unfinished(self) -> list[SessionItem]:
        return [i for i in self.items if i.state in RESUMABLE_STATES]

    def count(self, state: str) -> int:
        return sum(1 for i in self.items if i.state == state)

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.items),
            "queued": self.count(STATE_QUEUED),
            "active": self.count(STATE_ACTIVE),
            "completed": self.count(STATE_COMPLETED),
            "failed": self.count(STATE_FAILED),
            "cancelled": self.count(STATE_CANCELLED),
        }

    def remaining(self) -> int:
        return len(self.unfinished())

    def is_finished(self) -> bool:
        return len(self.items) > 0 and self.remaining() == 0 and self.count(STATE_ACTIVE) == 0

    def mark_active(self, item: SessionItem) -> None:
        item.state = STATE_ACTIVE
        item.progress = 0
        item.error = ""
        item.attempts += 1
        item.touch()

    def mark_completed(self, item: SessionItem, dest_paths: list[str], size_mb: float,
                       duration_sec: int) -> None:
        item.state = STATE_COMPLETED
        item.progress = 100
        item.error = ""
        item.dest_paths = dest_paths
        item.size_mb = size_mb
        item.duration_sec = duration_sec
        item.touch()

    def mark_failed(self, item: SessionItem, message: str) -> None:
        item.state = STATE_FAILED
        item.error = message[:500]
        item.touch()

    def reset_for_resume(self) -> None:
        """Return transient states to queued so a resume picks them up again."""
        for item in self.items:
            if item.state == STATE_ACTIVE:
                item.state = STATE_QUEUED
                item.progress = 0
                item.error = ""
                item.touch()
        self.touch()

    # ------------------------------------------------------------------
    #  Staging
    # ------------------------------------------------------------------

    @staticmethod
    def staging_root(output_dir: str) -> Path:
        return Path(output_dir) / ".cliprip_tmp"

    def staging_dir(self, item: SessionItem) -> Path:
        return self.staging_root(self.output_dir) / item.id
