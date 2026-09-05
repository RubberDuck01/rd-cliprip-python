import os
import webbrowser
from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rd_cliprip.controllers.download_manager import DownloadManager
from rd_cliprip.models.config import Config
from rd_cliprip.models.stats import Stats
from rd_cliprip.resources import get_resources_dir
from rd_cliprip.services.network import NetworkMonitor, country_flag
from rd_cliprip.ui.about_dialog import AboutDialog
from rd_cliprip.ui.donation_dialog import DonationDialog
from rd_cliprip.ui.downloads_table import DownloadsTable
from rd_cliprip.ui.ffmpeg_dialog import FfmpegDialog
from rd_cliprip.ui.settings_dialog import SettingsDialog
from rd_cliprip.ui.stats_dialog import StatsDialog
from rd_cliprip.ui.update_dialog import UpdateAvailableDialog
from rd_cliprip.ui.ytdlp_dialog import YtdlpDialog
from rd_cliprip.version import __version__


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: Config,
        stats: Stats,
        manager: DownloadManager,
        network_monitor: NetworkMonitor | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.stats = stats
        self.manager = manager
        self.network_monitor = network_monitor
        self.setWindowTitle("Rubber Duck's ClipRip")
        self.resize(940, 580)

        self._build_menu()
        self._build_ui()

        # Manager wiring
        self.manager.item_updated.connect(self._on_item_updated)
        self.manager.items_changed.connect(self._on_items_changed)
        self.manager.status_message.connect(self.set_status)
        self.manager.all_finished.connect(self._on_all_finished)
        self.manager.progress_updated.connect(self.table.update_progress)
        if self.manager.session is None:
            self.manager.new_session(self.config.downloads_dir)

        # Initial paint of the loaded/created session.
        self._on_items_changed()

        # Prompt to resume any leftover session.
        session = self.manager.session
        if session is not None and session.remaining() > 0:
            QTimer.singleShot(0, self._prompt_resume_session)

        self._setup_network_monitor()
        self._update_controls()
        self.set_status("Ready!")

    # ------------------------------------------------------------------
    #  Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        import_action = QAction("&Import URL List (.txt)...", self, triggered=self.import_url_list)
        import_action.setShortcut(QKeySequence("Ctrl+O"))
        file_menu.addAction(import_action)
        self._session_manager_action = QAction(
            "&Session Manager...", self, triggered=self.open_session_manager
        )
        self._session_manager_action.setShortcut(QKeySequence("Ctrl+M"))
        file_menu.addAction(self._session_manager_action)
        file_menu.addSeparator()
        open_action = QAction(
            "&Open Downloads Directory", self, triggered=self.open_downloads_directory
        )
        open_action.setShortcut(QKeySequence("Ctrl+E"))
        file_menu.addAction(open_action)
        settings_action = QAction("&Settings", self, triggered=self.open_settings)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("&Exit", self, triggered=self.close)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        file_menu.addAction(quit_action)

        # Edit
        edit_menu = menubar.addMenu("&Edit")
        clear_action = QAction("&Clear Finished Downloads", self, triggered=self.clear_finished)
        clear_action.setShortcut(QKeySequence("Ctrl+Shift+Del"))
        edit_menu.addAction(clear_action)
        edit_menu.addSeparator()
        self._clipboard_paste_action = QAction("&Auto-paste URL from Clipboard", self)
        self._clipboard_paste_action.setCheckable(True)
        self._clipboard_paste_action.setChecked(self.config.clipboard_paste_enabled)
        self._clipboard_paste_action.toggled.connect(self._on_clipboard_paste_toggled)
        edit_menu.addAction(self._clipboard_paste_action)

        # View
        view_menu = menubar.addMenu("&View")
        stats_action = QAction("&My Statistics", self, triggered=self.open_stats)
        stats_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        view_menu.addAction(stats_action)
        view_menu.addSeparator()
        self._always_on_top_action = QAction("&Always on Top", self)
        self._always_on_top_action.setCheckable(True)
        self._always_on_top_action.toggled.connect(self._on_always_on_top_toggled)
        view_menu.addAction(self._always_on_top_action)

        # Tools
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(
            QAction("&yt-dlp Settings", self, triggered=self.open_ytdlp_manager)
        )
        tools_menu.addAction(
            QAction("&FFmpeg Settings", self, triggered=self.open_ffmpeg_manager)
        )

        # Help
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(
            QAction("&Check for Updates", self, triggered=self.check_for_update)
        )
        help_menu.addSeparator()
        help_menu.addAction(
            QAction("&View Source on GitHub", self, triggered=self.visit_github)
        )
        help_menu.addAction(
            QAction("&About RD ClipRip", self, triggered=self.open_about)
        )
        help_menu.addAction(QAction("&About Qt", self, triggered=self.open_about_qt))

    # ------------------------------------------------------------------
    #  Central UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        # App header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(0, 0, 0, 8)
        branding_label = QLabel()
        branding_path = get_resources_dir() / "rd_cliprip_branding.png"
        if branding_path.exists():
            pix = QPixmap(str(branding_path))
            branding_label.setPixmap(
                pix.scaledToHeight(52, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            branding_label.setText("RD ClipRip")
            font = branding_label.font()
            font.setPointSize(font.pointSize() + 4)
            font.setBold(True)
            branding_label.setFont(font)
        branding_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(branding_label)
        subtitle_label = QLabel(
            "Powerful video downloader — Made with \u2665 by Rubber Duck"
        )
        subtitle_label.setEnabled(False)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle_label)
        layout.addLayout(header_layout)

        # Add-to-queue group
        add_group = QGroupBox("Add to Queue")
        add_form = QFormLayout(add_group)
        add_form.setContentsMargins(10, 12, 10, 10)
        add_form.setSpacing(6)

        self.format_hint_label = QLabel()
        hint_font = self.format_hint_label.font()
        hint_font.setItalic(True)
        hint_font.setPointSize(hint_font.pointSize() - 1)
        self.format_hint_label.setFont(hint_font)
        self.format_hint_label.setEnabled(False)
        self._update_format_hint()
        add_form.addRow(self.format_hint_label)

        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Paste a video / playlist URL, then click Add to Queue"
        )
        self.url_input.returnPressed.connect(self.on_add_clicked)
        url_row.addWidget(self.url_input, stretch=1)
        add_btn = QPushButton("Add to Queue")
        add_btn.clicked.connect(self.on_add_clicked)
        url_row.addWidget(add_btn)
        import_btn = QPushButton("Load .txt...")
        import_btn.clicked.connect(self.import_url_list)
        url_row.addWidget(import_btn)
        add_form.addRow("URL:", url_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.output_input = QLineEdit(self.config.downloads_dir)
        self.output_input.setReadOnly(True)
        out_row.addWidget(self.output_input, stretch=1)
        browse_btn = QPushButton("Choose...")
        browse_btn.clicked.connect(self.browse_output)
        out_row.addWidget(browse_btn)
        add_form.addRow("Download to:", out_row)

        layout.addWidget(add_group)

        # Queue group
        self.queue_group = QGroupBox("Download Queue")
        queue_layout = QVBoxLayout(self.queue_group)
        queue_layout.setContentsMargins(10, 12, 10, 10)
        queue_layout.setSpacing(6)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)
        self.start_btn = QPushButton("Start Downloads")
        self.start_btn.clicked.connect(self.manager.start)
        controls_row.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.manager.stop)
        controls_row.addWidget(self.stop_btn)
        controls_row.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setEnabled(False)
        controls_row.addWidget(self.summary_label)
        queue_layout.addLayout(controls_row)

        self.table = DownloadsTable()
        self.table.retry_requested.connect(self.manager.retry_item)
        self.table.cancel_requested.connect(self.manager.cancel_item)
        self.table.remove_requested.connect(self.manager.remove_item)
        self.table.open_folder_requested.connect(self._open_item_folder)
        self.table.open_file_requested.connect(self._open_item_file)
        queue_layout.addWidget(self.table, stretch=1)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_label = QLabel("Ready!")
        status_row.addWidget(self.status_label, stretch=1)
        clear_finished_btn = QPushButton("Clear Finished")
        clear_finished_btn.clicked.connect(self.clear_finished)
        status_row.addWidget(clear_finished_btn)
        discard_btn = QPushButton("Discard Session")
        discard_btn.clicked.connect(self.discard_session)
        status_row.addWidget(discard_btn)
        queue_layout.addLayout(status_row)

        layout.addWidget(self.queue_group, stretch=1)

        # Footer row
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(2, 0, 2, 0)
        made_with_label = QLabel("Made with \u2665 by Rubber Duck")
        made_with_label.setEnabled(False)
        footer_font = made_with_label.font()
        footer_font.setPointSize(footer_font.pointSize() - 1)
        made_with_label.setFont(footer_font)
        footer_row.addWidget(made_with_label)
        footer_row.addStretch()
        self.network_label = QLabel("Network: checking\u2026")
        self.network_label.setToolTip("Checking connectivity\u2026")
        self.network_label.setTextFormat(Qt.TextFormat.RichText)
        footer_row.addWidget(self.network_label)
        version_label = QLabel(f"Version {__version__}")
        version_label.setEnabled(False)
        version_label.setFont(footer_font)
        footer_row.addWidget(version_label)
        layout.addLayout(footer_row)

        self.setCentralWidget(root)

    # ------------------------------------------------------------------
    #  Network indicator
    # ------------------------------------------------------------------

    def _setup_network_monitor(self) -> None:
        if self.network_monitor is None or not self.config.network_indicator_enabled:
            self.network_label.hide()
            return
        self.network_monitor.status_changed.connect(self._on_network_status)
        self.network_monitor.start(self.config.network_poll_interval)

    def _on_network_status(self, status) -> None:
        self.network_label.setText(self._network_pill_html(status))
        self.network_label.setToolTip(status.tooltip())
        color = "#2e7d32" if status.connected else "#c62828"
        self.network_label.setStyleSheet(f"color: {color};")

    @staticmethod
    def _network_pill_html(status) -> str:
        """Rich-text pill. The flag glyph is wrapped in Segoe UI Emoji so Windows
        renders it as an emoji flag where supported; otherwise it degrades to
        showing the two-letter code."""
        if not status.connected:
            return "&#9679; Offline"
        parts = ["&#9679; Online"]
        if status.ip:
            parts.append(escape(status.ip))
        flag = country_flag(status.country_code)
        if flag:
            parts.append(
                f'<span style="font-family: \'Segoe UI Emoji\';">{flag}</span>'
            )
        elif status.country_code:
            parts.append(escape(status.country_code))
        text = "  &middot;  ".join(parts)
        if status.vpn_hint:
            text += "  <i>(VPN)</i>"
        return text

    # ------------------------------------------------------------------
    #  Events
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.manager.running:
            answer = QMessageBox.question(
                self,
                "Downloads in progress",
                "Downloads are still running.\n\nStop them and resume later?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.manager.stop()
        self.show_donation_popup()
        event.accept()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            if self.network_monitor is not None and self.config.network_indicator_enabled:
                self.network_monitor.check_now()
            if self.config.clipboard_paste_enabled and not self.url_input.text().strip():
                text = QApplication.clipboard().text().strip()
                if text.startswith("http"):
                    self.url_input.setText(text)
                    self.set_status("URL pasted from clipboard.")
        super().changeEvent(event)

    def _on_clipboard_paste_toggled(self, checked: bool) -> None:
        self.config.set_clipboard_paste_enabled(checked)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ------------------------------------------------------------------
    #  Queue actions
    # ------------------------------------------------------------------

    def on_add_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            self.set_status("Invalid URL!")
            return
        added = self.manager.add_urls([url])
        if added:
            self.url_input.clear()
            self.set_status("Added to queue. Press Start Downloads to begin.")
            self._on_items_changed()

    def import_url_list(self) -> None:
        if self.manager.running:
            answer = QMessageBox.question(
                self,
                "Start a new list?",
                "Downloads are running. Starting a new list pauses the current "
                "session (it can be resumed later).\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Select URL List (.txt)", "", "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        count, duplicates = self.manager.import_txt(path, self.output_input.text())
        if count:
            message = f"Imported <b>{count}</b> URL(s) into a new session."
            if duplicates:
                message += (
                    f"<br><br><b>{duplicates}</b> duplicate(s) were found "
                    "and removed automatically."
                )
            message += "<br><br>Press <b>Start Downloads</b> to begin."
            QMessageBox.information(self, "URL List Imported", message)
        else:
            self.set_status("No valid URLs found in that file.")
            if duplicates:
                QMessageBox.information(
                    self,
                    "URL List Imported",
                    f"The file contained only <b>{duplicates}</b> duplicate(s), "
                    "which were removed.",
                )

    def open_session_manager(self) -> None:
        from rd_cliprip.ui.session_manager_dialog import SessionManagerDialog

        SessionManagerDialog(self, self.manager, self.import_url_list).exec()

    def _prompt_resume_session(self) -> None:
        session = self.manager.session
        if session is None:
            return
        remaining = session.remaining()
        answer = QMessageBox.question(
            self,
            "Resume previous session?",
            f"A previous download session with <b>{remaining}</b> item(s) still pending "
            "was found.<br><br>Resume where you left off?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.manager.start()

    def clear_finished(self) -> None:
        self.manager.clear_finished()
        self.set_status("Cleared finished downloads.")

    def discard_session(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete session?",
            "This deletes the current session and all its progress.\n\n"
            "Downloads in progress will be stopped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.discard_session()
        self.set_status("Session deleted. Started an empty session.")

    # ------------------------------------------------------------------
    #  Manager-driven UI updates
    # ------------------------------------------------------------------

    def _session_items(self):
        return self.manager.session.items if self.manager.session else []

    def _on_item_updated(self, item_id: str) -> None:
        session = self.manager.session
        if session is None:
            return
        item = session.get_item(item_id)
        if item is not None:
            self.table.update_item(item)

    def _on_items_changed(self) -> None:
        session = self.manager.session
        items = session.items if session else []
        self.table.refresh_items(items)
        self._update_summary()
        self._sync_session_ui()
        self._update_controls()

    def _sync_session_ui(self) -> None:
        """Show which session is active and which folder it downloads into."""
        session = self.manager.session
        if session is None:
            self.queue_group.setTitle("Download Queue")
            self.output_input.setText(self.config.downloads_dir)
            return
        label = session.label or "Untitled"
        title = label if len(label) <= 60 else label[:57] + "\u2026"
        self.queue_group.setTitle(f"Download Queue \u2014 {title}")
        self.output_input.setText(session.output_dir or self.config.downloads_dir)

    def _on_all_finished(self) -> None:
        self._update_controls()

    def _update_summary(self) -> None:
        session = self.manager.session
        if session is None:
            self.summary_label.setText("")
            return
        counts = session.counts()
        self.summary_label.setText(
            f"{counts['completed']}/{counts['total']} done"
            + (f"  ·  {counts['active']} active" if counts["active"] else "")
            + (f"  ·  {counts['failed']} failed" if counts["failed"] else "")
            + (f"  ·  {counts['cancelled']} cancelled" if counts["cancelled"] else "")
            + (f"  ·  {counts['queued']} queued" if counts["queued"] else "")
        )

    def _update_controls(self) -> None:
        running = self.manager.running
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _open_item_folder(self, item_id: str) -> None:
        path = self.table.item_dest_paths(item_id)
        if path:
            self.open_downloads_directory(path[0])

    def _open_item_file(self, item_id: str) -> None:
        paths = self.table.item_dest_paths(item_id)
        if not paths:
            return
        file_path = Path(paths[0])
        if not file_path.exists():
            self.set_status("The downloaded file no longer exists.")
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))
        except Exception as ex:
            self.set_status(f"Failed to open file: {ex}")

    # ------------------------------------------------------------------
    #  Output directory helpers
    # ------------------------------------------------------------------

    def browse_output(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Downloads Directory", self.output_input.text()
        )
        if not directory:
            return
        session = self.manager.session
        if session is None:
            self.config.set_downloads_dir(directory)
            self.output_input.setText(directory)
            return
        # The folder is a property of the active session, not a global default.
        self.manager.edit_session(session.id, output_dir=directory)
        self.set_status(f"Download folder for this session changed to {directory}")

    def open_downloads_directory(self, raw_path: str | None = None) -> None:
        raw = raw_path or (self.output_input.text() or self.config.downloads_dir).strip()
        path = Path(raw)

        if not path.exists():
            self.set_status("Downloads directory does not exist.")
            return

        folder = path if path.is_dir() else path.parent
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except Exception as ex:
            self.set_status(f"Failed to open directory: {ex}")

    # ------------------------------------------------------------------
    #  Status helpers
    # ------------------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    #  Dialogs & helpers
    # ------------------------------------------------------------------

    def _update_format_hint(self) -> None:
        fmt = self.config.preferred_format.upper()
        res = self.config.preferred_resolution
        sub = " + subs" if self.config.embed_subs else ""
        self.format_hint_label.setText(f"Downloading: {fmt} up to {res}{sub}")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.config)
        if dialog.exec():
            # Settings' folder is the default for NEW sessions; also adopt it for
            # a still-blank ad-hoc session that has no txt source yet.
            session = self.manager.session
            if (
                session is not None
                and not session.source_file
                and not session.items
                and session.output_dir
            ):
                self.manager.edit_session(session.id, output_dir=self.config.downloads_dir)
            self._sync_session_ui()
            self._update_format_hint()
            self._apply_network_preferences()
            self.set_status("Settings saved!")
            self._update_controls()

    def _apply_network_preferences(self) -> None:
        if self.network_monitor is None:
            return
        if self.config.network_indicator_enabled:
            self.network_monitor.set_interval(self.config.network_poll_interval)
            if not self.network_label.isVisible():
                self.network_label.show()
            self.network_monitor.check_now()
        else:
            self.network_label.hide()

    def open_ytdlp_manager(self) -> None:
        YtdlpDialog(self).exec()

    def open_ffmpeg_manager(self) -> None:
        FfmpegDialog(self).exec()

    def visit_github(self) -> None:
        webbrowser.open("https://github.com/RubberDuck01/rd-cliprip-python")

    def open_about(self) -> None:
        AboutDialog(self, config=self.config).exec()

    def open_about_qt(self) -> None:
        QMessageBox.aboutQt(self)

    def open_stats(self) -> None:
        StatsDialog(self, self.stats).exec()

    def show_donation_popup(self) -> None:
        if not self.config.i_have_donated:
            DonationDialog(self).exec()

    def show_update_available(self, latest_version: str) -> None:
        UpdateAvailableDialog(self, latest_version=latest_version).exec()

    def show_up_to_date(self) -> None:
        QMessageBox.information(
            self, "RD ClipRip", "You're already on the latest version!"
        )

    def check_for_update(self) -> None:
        self.controller._check_for_app_update(manual=True)
