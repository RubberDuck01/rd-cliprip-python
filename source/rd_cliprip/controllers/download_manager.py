import queue
import shutil
import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rd_cliprip.models.config import Config
from rd_cliprip.models.stats import Stats
from rd_cliprip.models.session import (
    RESUMABLE_STATES,
    STATE_CANCELLED,
    STATE_COMPLETED,
    STATE_QUEUED,
    DownloadSession,
    SessionItem,
)
from rd_cliprip.services.downloader import (
    find_ffmpeg_exe,
    run_single_item,
)

_POLL_INTERVAL_MS = 80


class DownloadManager(QObject):
    """Runs a resumable URL session across a pool of concurrent agents.

    The manager is the single owner of the active ``DownloadSession`` and all
    session mutation happens on the GUI thread.  Downloads themselves run in
    plain worker threads that pull item ids from a job queue and report back
    through a results queue which the manager drains on a timer.
    """

    item_updated = pyqtSignal(str)  # item_id
    items_changed = pyqtSignal()  # queue composition changed
    status_message = pyqtSignal(str)
    all_finished = pyqtSignal()

    def __init__(self, config: Config, stats: Stats) -> None:
        super().__init__()
        self.config = config
        self.stats = stats
        self.session: DownloadSession | None = None

        self._running = False
        self._stop = threading.Event()
        self._jobs: queue.Queue[str | None] = queue.Queue()
        self._results: queue.Queue[dict[str, Any]] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._busy = 0  # number of worker threads currently inside a download
        self._procs: dict[str, Any] = {}  # item_id -> Popen
        self._kill_cause: dict[str, str] = {}  # item_id -> 'stop' | 'cancel' | 'remove'

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll_results)
        self._timer.start()

    # ------------------------------------------------------------------
    #  Session management
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    def set_session(self, session: DownloadSession | None) -> None:
        self.stop()
        self.session = session
        if session is not None:
            session.save()
        self.items_changed.emit()

    def new_session(self, output_dir: str, source_file: str = "") -> DownloadSession:
        """Archive any unfinished session and start a fresh one."""
        if self.session is not None and self.session.remaining() > 0:
            self.session.archive()
        session = DownloadSession(output_dir=output_dir, source_file=source_file)
        self.set_session(session)
        return session

    def load_last_session(self) -> DownloadSession | None:
        session = DownloadSession.load()
        if session is not None:
            self.set_session(session)
        return session

    # ------------------------------------------------------------------
    #  Adding URLs
    # ------------------------------------------------------------------

    def add_urls(self, urls: list[str]) -> list[SessionItem]:
        if self.session is None:
            self.session = DownloadSession(output_dir=self.config.downloads_dir)
        clean: list[str] = []
        seen: set[str] = set()
        for u in urls:
            u = u.strip()
            if not u:
                continue
            if u in seen:
                continue
            seen.add(u)
            clean.append(u)
        if not clean:
            return []
        added = self.session.add_urls(clean)
        self.session.save()
        if self._running:
            # A running pool will pick up new entries as agents free up.
            for item in added:
                self._jobs.put(item.id)
        self.items_changed.emit()
        return added

    def import_txt(self, path: str, output_dir: str | None = None) -> tuple[int, int]:
        """Import a .txt file of URLs (one per line) as a new session.

        Duplicate URLs inside the file are removed automatically.
        Returns (number of URLs imported, number of duplicates dropped).
        """
        txt = Path(path)
        if not txt.exists():
            return 0, 0
        raw = [
            line.strip()
            for line in txt.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        unique: list[str] = []
        seen: set[str] = set()
        duplicates = 0
        for url in raw:
            if url in seen:
                duplicates += 1
                continue
            seen.add(url)
            unique.append(url)
        if not unique:
            return 0, duplicates
        session = self.new_session(
            output_dir=output_dir or self.config.downloads_dir, source_file=str(txt)
        )
        session.add_urls(unique)
        session.save()
        self.items_changed.emit()
        return len(unique), duplicates

    # ------------------------------------------------------------------
    #  Transport controls
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Begin (or resume) downloads for the current session."""
        if self._running or self.session is None:
            return False

        # Make sure any straggler threads from a previous run are gone.
        self._stop.set()
        self._join_threads()
        self._drain_results()
        self._stop.clear()
        self._kill_cause.clear()

        # Anything left in a transient 'active' state (crash/restart) goes back
        # to queued so it is retried from its partial file.
        self.session.reset_for_resume()

        pending = [
            i for i in self.session.items if i.state in RESUMABLE_STATES
        ]
        if not pending:
            return False

        # Reset any previously failed/cancelled entries so the UI reads cleanly.
        for item in pending:
            if item.state != STATE_QUEUED:
                item.state = STATE_QUEUED
                item.error = ""
                item.touch()
        self.session.save()

        concurrency = max(1, self.config.max_concurrent_downloads)
        agent_count = min(concurrency, len(pending))

        for item in pending:
            self._jobs.put(item.id)

        self._threads = []
        for _ in range(agent_count):
            thread = threading.Thread(target=self._worker_loop, daemon=True)
            thread.start()
            self._threads.append(thread)

        self._running = True
        self.status_message.emit(
            f"Downloading {len(pending)} item(s) with {agent_count} agent(s)..."
        )
        self.items_changed.emit()
        return True

    def stop(self) -> None:
        """Stop all downloads. Items keep their place and can be resumed later."""
        if not self._running:
            return

        self._stop.set()
        with self._lock:
            for item_id, proc in list(self._procs.items()):
                self._kill_cause[item_id] = "stop"
                try:
                    proc.kill()
                except Exception:
                    pass

        if self.session is not None:
            self.session.reset_for_resume()
            self.session.save()

        self._join_threads()
        self._drain_results()

        self._running = False
        self.status_message.emit("Downloads paused. Items will resume next time.")
        self.items_changed.emit()

    def cancel_item(self, item_id: str) -> None:
        """Stop a single running download now (kept in the list as cancelled)."""
        with self._lock:
            proc = self._procs.get(item_id)
            if proc is not None:
                self._kill_cause[item_id] = "cancel"
                try:
                    proc.kill()
                except Exception:
                    pass
                return
        item = self.session.get_item(item_id) if self.session else None
        if item is not None and item.state in RESUMABLE_STATES:
            item.state = STATE_CANCELLED
            item.error = ""
            item.touch()
            self.session.save()
            self.item_updated.emit(item_id)

    def retry_item(self, item_id: str) -> None:
        item = self.session.get_item(item_id) if self.session else None
        if item is None:
            return
        item.state = STATE_QUEUED
        item.error = ""
        item.progress = 0
        item.touch()
        self.session.save()
        if self._running:
            self._jobs.put(item.id)
        self.item_updated.emit(item_id)

    def remove_item(self, item_id: str) -> None:
        if self.session is None:
            return
        with self._lock:
            proc = self._procs.get(item_id)
            if proc is not None:
                self._kill_cause[item_id] = "remove"
                try:
                    proc.kill()
                except Exception:
                    pass
        self.session.items = [i for i in self.session.items if i.id != item_id]
        self.session.save()
        self.items_changed.emit()

    def clear_finished(self) -> None:
        if self.session is None:
            return
        self.session.items = [
            i for i in self.session.items if i.state != STATE_COMPLETED
        ]
        self.session.save()
        self.items_changed.emit()

    def discard_session(self) -> None:
        """Remove the active session file entirely (finished or not)."""
        self.stop()
        if self.session is not None:
            self.session.clear_file()
            self.session = None
        self.items_changed.emit()

    # ------------------------------------------------------------------
    #  Worker machinery
    # ------------------------------------------------------------------

    def _mark_busy(self) -> None:
        with self._lock:
            self._busy += 1

    def _mark_idle(self) -> None:
        with self._lock:
            self._busy = max(0, self._busy - 1)

    def _register_proc(self, item_id: str, proc: Any) -> None:
        with self._lock:
            self._procs[item_id] = proc

    def _unregister_proc(self, item_id: str) -> None:
        with self._lock:
            self._procs.pop(item_id, None)

    def _join_threads(self) -> None:
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads = []

    def _drain_results(self) -> None:
        while True:
            try:
                self._results.get_nowait()
            except queue.Empty:
                break

    def _on_progress(self, item_id: str, percent: int) -> None:
        self._results.put({"kind": "progress", "item_id": item_id, "percent": percent})

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item_id = self._jobs.get(timeout=0.25)
            except queue.Empty:
                continue
            if item_id is None:
                break

            if self.session is None:
                break
            item = self.session.get_item(item_id)
            if item is None or item.state not in RESUMABLE_STATES:
                continue

            self._mark_busy()
            try:
                self._results.put({"kind": "started", "item_id": item_id})
                ffmpeg = find_ffmpeg_exe()
                result = run_single_item(
                    item_id=item.id,
                    url=item.url,
                    staging_dir=self.session.staging_dir(item),
                    output_dir=self.session.output_dir,
                    preferred_format=self.config.preferred_format,
                    preferred_resolution=self.config.preferred_resolution,
                    embed_subs=self.config.embed_subs,
                    cookies_enabled=self.config.cookies_enabled,
                    cookies_path=self.config.cookies_path,
                    allow_playlist=True,
                    remux_to_mp4=self.config.remux_to_mp4 and ffmpeg is not None,
                    ffmpeg_location=str(Path(ffmpeg).parent) if ffmpeg else None,
                    ffmpeg_exe=ffmpeg,
                    on_progress=self._on_progress,
                    register_proc=self._register_proc,
                    unregister_proc=self._unregister_proc,
                )
                result["kind"] = "result"
                self._results.put(result)
            finally:
                self._mark_idle()

    def _poll_results(self) -> None:
        if self.session is None:
            return

        while True:
            try:
                msg = self._results.get_nowait()
            except queue.Empty:
                break
            self._handle_result(msg)

        self._try_finish_run()

    def _handle_result(self, msg: dict[str, Any]) -> None:
        item = self.session.get_item(str(msg.get("item_id", ""))) if self.session else None
        if item is None:
            return

        kind = msg.get("kind")

        if kind == "started":
            self.session.mark_active(item)
            self.session.save()
            self.item_updated.emit(item.id)
            self.items_changed.emit()
            return

        if kind == "progress":
            item.progress = int(msg.get("percent", item.progress))
            self.item_updated.emit(item.id)
            return

        if kind == "result":
            cause = self._kill_cause.pop(item.id, None)
            status = msg.get("status")

            if cause == "cancel":
                item.state = STATE_CANCELLED
                item.error = "Cancelled by user."
                item.touch()
            elif cause == "remove":
                pass  # row is already gone; nothing to update
            elif cause == "stop":
                pass  # stop() already reset the item to queued
            elif status == "completed":
                dest_paths = list(msg.get("dest_paths") or [])
                size_mb = float(msg.get("size_mb", 0.0))
                duration_sec = int(msg.get("duration_sec", 0))
                self.stats.add_successful_download(
                    size_mb=size_mb,
                    duration_sec=duration_sec,
                    file_count=max(1, len(dest_paths)),
                )
                self.session.mark_completed(
                    item,
                    dest_paths=dest_paths,
                    size_mb=size_mb,
                    duration_sec=duration_sec,
                )
                try:
                    staging = self.session.staging_dir(item)
                    if staging.exists():
                        shutil.rmtree(staging, ignore_errors=True)
                except Exception:
                    pass
            else:
                self.session.mark_failed(item, str(msg.get("message", "Download failed.")))

            self.session.save()
            self.item_updated.emit(item.id)
            self.items_changed.emit()

    def _try_finish_run(self) -> None:
        """End the run once every queued/in-flight item has resolved."""
        if not self._running:
            return
        with self._lock:
            busy = self._busy
            has_procs = bool(self._procs)
        if busy or has_procs or not self._jobs.empty() or not self._results.empty():
            return

        self._running = False
        self._stop.set()
        self._join_threads()

        remaining = self.session.remaining() if self.session else 0
        if remaining == 0:
            self.status_message.emit("All downloads finished!")
            self.all_finished.emit()
        else:
            self.status_message.emit(
                f"Finished with {remaining} item(s) left to retry."
            )
        self.items_changed.emit()
