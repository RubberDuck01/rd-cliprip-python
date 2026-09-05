from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from rd_cliprip.models.config import Config


class SettingsDialog(QDialog):
    def __init__(self, parent, config: Config) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("RD ClipRip - Settings")
        self.resize(520, 320)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Destination group
        dest_group = QGroupBox("Destination")
        dest_form = QFormLayout(dest_group)
        dest_form.setContentsMargins(10, 12, 10, 10)
        dest_form.setSpacing(6)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.dir_input = QLineEdit(self.config.downloads_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_input, stretch=1)
        dir_row.addWidget(browse_btn)
        dest_form.addRow("Downloads directory:", dir_row)
        layout.addWidget(dest_group)

        # Processing group
        proc_group = QGroupBox("Video Processing")
        proc_form = QFormLayout(proc_group)
        proc_form.setContentsMargins(10, 12, 10, 10)
        proc_form.setSpacing(6)

        self.auto_update_check = QCheckBox("Auto-update yt-dlp on launch")
        self.auto_update_check.setChecked(self.config.auto_update)
        proc_form.addRow(self.auto_update_check)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MKV", "WebM"])
        fmt = self.config.preferred_format.lower()
        idx = {"mp4": 0, "mkv": 1, "webm": 2}.get(fmt, 0)
        self.format_combo.setCurrentIndex(idx)
        proc_form.addRow("Video format:", self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"])
        res = self.config.preferred_resolution.lower().replace("p", "")
        res_map = {"2160": 0, "1440": 1, "1080": 2, "720": 3, "480": 4, "360": 5}
        self.resolution_combo.setCurrentIndex(res_map.get(res, 2))
        proc_form.addRow("Max resolution:", self.resolution_combo)

        self.embed_subs_check = QCheckBox("Embed subtitles when available")
        self.embed_subs_check.setChecked(self.config.embed_subs)
        proc_form.addRow(self.embed_subs_check)

        layout.addWidget(proc_group)

        # Cookies group
        cookies_group = QGroupBox("Cookies (for restricted content)")
        cookies_form = QFormLayout(cookies_group)
        cookies_form.setContentsMargins(10, 12, 10, 10)
        cookies_form.setSpacing(6)

        self.cookies_enabled_check = QCheckBox("Enable cookies")
        self.cookies_enabled_check.setChecked(self.config.cookies_enabled)
        self.cookies_enabled_check.toggled.connect(self._on_cookies_toggled)
        cookies_form.addRow(self.cookies_enabled_check)

        cookies_row = QHBoxLayout()
        cookies_row.setSpacing(6)
        self.cookies_path_input = QLineEdit(self.config.cookies_path)
        self.cookies_path_input.setEnabled(self.config.cookies_enabled)
        cookies_browse_btn = QPushButton("Browse...")
        cookies_browse_btn.setEnabled(self.config.cookies_enabled)
        cookies_browse_btn.clicked.connect(self._browse_cookies)
        cookies_row.addWidget(self.cookies_path_input, stretch=1)
        cookies_row.addWidget(cookies_browse_btn)
        self._cookies_row_widgets = [self.cookies_path_input, cookies_browse_btn]
        cookies_form.addRow("Cookies file:", cookies_row)

        layout.addWidget(cookies_group)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Downloads Directory")
        if path:
            self.dir_input.setText(path)

    def _browse_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cookies File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.cookies_path_input.setText(path)

    def _on_cookies_toggled(self, enabled: bool) -> None:
        for w in self._cookies_row_widgets:
            w.setEnabled(enabled)

    def _save_and_close(self) -> None:
        self.config.set_downloads_dir(self.dir_input.text())
        self.config.set_auto_update(self.auto_update_check.isChecked())
        self.config.set_preferred_format(self.format_combo.currentText().lower())
        res_text = self.resolution_combo.currentText().split()[0].lower().replace("p", "")
        self.config.set_preferred_resolution(f"{res_text}p")
        self.config.set_embed_subs(self.embed_subs_check.isChecked())
        self.config.set_cookies_enabled(self.cookies_enabled_check.isChecked())
        self.config.set_cookies_path(self.cookies_path_input.text())
        self.accept()
