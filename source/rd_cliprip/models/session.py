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


def _app_data_dir() -> Path:
    """Return the app data dir shared with Stats."""
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".config"
    return base / "Rubber Duck Softworks" / "ClipRip" / "Data"


def sessions_dir() -> Path:
    return _app_data_dir() / "sessions"


def _active_file() -> Path:
    return _app_data_dir() / "active_session.txt"


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"session_{session_id}.json"


def list_sessions() -> list[dict[str, Any]]:
    """Return metadata for every stored session, newest first."""
    try:
        files = sorted(
            sessions_dir().glob("session_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        files = []

    result: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = payload.get("items", [])
        states = [i.get("state", STATE_QUEUED) for i in items]
        result.append(
            {
                "id": payload.get("id", path.stem.replace("session_", "")),
                "label": payload.get("label", ""),
                "output_dir": payload.get("output_dir", ""),
                "source_file": payload.get("source_file", ""),
                "created_at": payload.get("created_at", ""),
                "total": len(items),
                "completed": states.count(STATE_COMPLETED),
                "remaining": sum(1 for s in states if s in RESUMABLE_STATES),
            }
        )
    return result


def delete_session_file(session_id: str) -> None:
    try:
        path = session_path(session_id)
        if path.exists():
            path.unlink()
    except Exception:
        pass


def set_active_session(session_id: str) -> None:
    try:
        _active_file().parent.mkdir(parents=True, exist_ok=True)
        _active_file().write_text(session_id, encoding="utf-8")
    except Exception:
        pass


def clear_active_session() -> None:
    try:
        if _active_file().exists():
            _active_file().unlink()
    except Exception:
        pass


def get_active_session_id() -> str | None:
    try:
        if _active_file().exists():
            value = _active_file().read_text(encoding="utf-8").strip()
            return value if value else None
    except Exception:
        pass
    return None


class DownloadSession:
    """A persistent, resumable queue of URLs to download.

    Each session is stored as its own file under the data dir's ``sessions/``
    folder, identified by a unique id.  One session can be active at a time;
    the rest stay saved on disk and can be reopened or deleted.
    """

    def __init__(
        self,
        output_dir: str = "",
        source_file: str = "",
        label: str = "",
        session_id: str | None = None,
    ) -> None:
        self.id = session_id or uuid.uuid4().hex[:12]
        self.label = label or self._default_label(source_file)
        self.output_dir = output_dir
        self.source_file = source_file
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.items: list[SessionItem] = []

    @staticmethod
    def _default_label(source_file: str) -> str:
        if source_file:
            name = Path(source_file).stem.strip()
            if name:
                return name
        return f"Session {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------

    @property
    def file_path(self) -> Path:
        return session_path(self.id)

    def save(self) -> None:
        self.updated_at = datetime.now().isoformat()
        payload = {
            "version": 1,
            "id": self.id,
            "label": self.label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "output_dir": self.output_dir,
            "source_file": self.source_file,
            "items": [i.to_dict() for i in self.items],
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, session_id: str) -> "DownloadSession | None":
        path = session_path(session_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        session = cls(
            output_dir=str(payload.get("output_dir", "")),
            source_file=str(payload.get("source_file", "")),
            label=str(payload.get("label", "")),
            session_id=str(payload.get("id", session_id)),
        )
        session.created_at = str(payload.get("created_at", session.created_at))
        session.updated_at = str(payload.get("updated_at", session.updated_at))
        session.items = [SessionItem.from_dict(d) for d in payload.get("items", [])]
        return session

    @classmethod
    def load_legacy(cls) -> "DownloadSession | None":
        """Import the pre-session-manager singleton file (Data/session.json)."""
        legacy = _app_data_dir() / "session.json"
        if not legacy.exists():
            return None
        try:
            payload = json.loads(legacy.read_text(encoding="utf-8"))
        except Exception:
            return None
        session = cls(
            output_dir=str(payload.get("output_dir", "")),
            source_file=str(payload.get("source_file", "")),
        )
        session.created_at = str(payload.get("created_at", session.created_at))
        session.items = [SessionItem.from_dict(d) for d in payload.get("items", [])]
        return session

    def delete_file(self) -> None:
        delete_session_file(self.id)

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    # ------------------------------------------------------------------
    #  Items
    # ------------------------------------------------------------------

    def add_url(self, url: str) -> SessionItem:
        item = SessionItem(url=url.strip())
        self.items.append(item)
        self.touch()
        return item

    def add_urls(self, urls: list[str]) -> list[SessionItem]:
        return [self.add_url(u) for u in urls]

    def get_item(self, item_id: str) -> SessionItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def next_queued(self) -> SessionItem | None:
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
