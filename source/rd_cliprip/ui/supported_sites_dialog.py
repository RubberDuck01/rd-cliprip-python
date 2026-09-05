import threading
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from rd_cliprip.services import supported_sites


class SupportedSitesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Supported Websites")
        self.setModal(True)
        self.resize(560, 620)

        self._sites: list[str] = []
        self._fetched_at: str = ""
        self._thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.info_label = QLabel()
        self.info_label.setEnabled(False)
        layout.addWidget(self.info_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search supported websites...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget, stretch=1)

        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setEnabled(False)
        layout.addWidget(self.empty_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()
        self.fetch_btn = QPushButton("Fetch Again...")
        self.fetch_btn.clicked.connect(self._start_fetch)
        btn_row.addWidget(self.fetch_btn)
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(150)
        self._poll_timer.timeout.connect(self._poll_fetch)

        self._load_cache()
        if not self._sites:
            self._start_fetch()
        self._apply_filter()

    # ------------------------------------------------------------------
    #  Cache / fetch
    # ------------------------------------------------------------------

    def _load_cache(self) -> None:
        cached = supported_sites.load_cache()
        self._sites = list(cached.get("sites") or []) if cached else []
        self._fetched_at = (cached or {}).get("fetched_at", "")
        self._refresh_info()

    def _refresh_info(self) -> None:
        count = len(self._sites)
        if self._fetched_at:
            try:
                when = datetime.fromisoformat(self._fetched_at).strftime("%Y-%m-%d %H:%M")
            except Exception:
                when = self._fetched_at
            self.info_label.setText(
                f"{count} supported websites  \u2022  list fetched {when}"
            )
        elif count:
            self.info_label.setText(f"{count} supported websites")
        else:
            self.info_label.setText("The supported-websites list has not been downloaded yet.")

    def _start_fetch(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.info_label.setText("Fetching the supported-websites list...")
        self._thread = threading.Thread(target=self._do_fetch, daemon=True)
        self._thread.start()
        self._poll_timer.start()

    def _do_fetch(self) -> None:
        supported_sites.fetch_and_cache()

    def _poll_fetch(self) -> None:
        if self._thread is None:
            return
        if self._thread.is_alive():
            return
        self._poll_timer.stop()
        self._thread = None
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Again...")
        if not supported_sites.load_cache():
            # Fetch failed and nothing cached yet.
            self.info_label.setText("Could not fetch the supported-websites list.")
            QMessageBox.warning(
                self,
                "Fetch failed",
                "Could not download the supported-websites list.\n"
                "Check your connection and try again.",
            )
        self._load_cache()
        self._apply_filter()

    # ------------------------------------------------------------------
    #  Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self) -> None:
        query = self.search_input.text().strip().lower()
        self.list_widget.clear()

        if not self._sites:
            self.empty_label.setText(
                "No list loaded yet \u2014 click 'Fetch Again...' to download it."
                if not self._thread
                else "Fetching list..."
            )
            self.empty_label.setVisible(True)
            return

        if not query:
            matches = self._sites
        else:
            matches = [s for s in self._sites if query in s.lower()]

        for site in matches:
            self.list_widget.addItem(site)

        if matches:
            self.empty_label.clear()
            self.empty_label.setVisible(False)
        else:
            self.empty_label.setText(
                f'No supported websites match "{self.search_input.text().strip()}".'
            )
            self.empty_label.setVisible(True)
