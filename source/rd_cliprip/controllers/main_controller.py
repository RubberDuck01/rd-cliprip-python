from PyQt6.QtCore import QObject, QThread, pyqtSignal

from rd_cliprip.services.downloader import find_ytdlp_exe, update_ytdlp
from rd_cliprip.services.updater import check_for_app_update


class AutoUpdateWorker(QObject):
    finished = pyqtSignal(str)  # status message for the window

    def run(self) -> None:
        ok, _ = update_ytdlp()
        if ok:
            self.finished.emit("yt-dlp is up to date, ClipRip ready!")
        else:
            self.finished.emit(
                "yt-dlp auto-update failed. Go to Tools → yt-dlp Settings to update manually."
            )


class UpdateCheckerWorker(QObject):
    finished = pyqtSignal(bool, str)  # (update_available, latest_version)

    def run(self) -> None:
        available, version = check_for_app_update()
        self.finished.emit(available, version)


class MainController(QObject):
    """App-level wiring: update checks and tool readiness.

    Download orchestration lives in DownloadManager; the main window talks to
    the manager directly for everything queue related.
    """

    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self._update_check_manual: bool = False

        self._maybe_auto_update_ytdlp()
        self._check_for_app_update(manual=False)

    # ------------------------------------------------------------------
    #  yt-dlp auto-update on launch
    # ------------------------------------------------------------------

    def _maybe_auto_update_ytdlp(self) -> None:
        if not self.window.config.auto_update:
            return
        if not find_ytdlp_exe():
            self.window.set_status(
                "yt-dlp is not installed. Go to Tools → yt-dlp Settings to install it first."
            )
            return
        self.window.set_status("Checking for yt-dlp updates...")
        self._au_thread = QThread()
        self._au_worker = AutoUpdateWorker()
        self._au_worker.moveToThread(self._au_thread)
        self._au_thread.started.connect(self._au_worker.run)
        self._au_worker.finished.connect(self.window.set_status)
        self._au_worker.finished.connect(self._au_thread.quit)
        self._au_thread.finished.connect(self._au_thread.deleteLater)
        self._au_thread.start()

    # ------------------------------------------------------------------
    #  App update check
    # ------------------------------------------------------------------

    def _check_for_app_update(self, manual: bool = False) -> None:
        self._update_check_manual = manual
        self._uc_thread = QThread()
        self._uc_worker = UpdateCheckerWorker()
        self._uc_worker.moveToThread(self._uc_thread)
        self._uc_thread.started.connect(self._uc_worker.run)
        self._uc_worker.finished.connect(self._on_update_checked)
        self._uc_worker.finished.connect(self._uc_thread.quit)
        self._uc_thread.finished.connect(self._uc_thread.deleteLater)
        self._uc_thread.start()

    def _on_update_checked(self, update_available: bool, latest_version: str) -> None:
        if update_available:
            self.window.show_update_available(latest_version)
        elif self._update_check_manual:
            self.window.show_up_to_date()
