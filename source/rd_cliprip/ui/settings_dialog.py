from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from rd_cliprip.models.config import Config


class SettingsDialog(QDialog):
    def __init__(self, parent, config: Config) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("RD ClipRip - Settings")
        self.resize(620, 860)
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

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 8)
        self.concurrent_spin.setValue(self.config.max_concurrent_downloads)
        concurrent_hint = QLabel("(used only for multi-URL lists)")
        concurrent_hint.setEnabled(False)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.concurrent_spin)
        row.addWidget(concurrent_hint)
        row.addStretch()
        proc_form.addRow("Simultaneous downloads:", row)

        self.remux_check = QCheckBox("Remux completed videos to MP4 (optional, needs FFmpeg)")
        self.remux_check.setChecked(self.config.remux_to_mp4)
        proc_form.addRow(self.remux_check)
        remux_desc = QLabel(
            "Off by default: MP4 already prefers H.264/AAC files, which play and "
            "show thumbnails everywhere (MEGA, phones, etc.). Turn this on only "
            "if you want to force other sources into an MP4 container."
        )
        remux_desc.setWordWrap(True)
        remux_desc.setEnabled(False)
        remux_desc_font = remux_desc.font()
        remux_desc_font.setPointSize(remux_desc_font.pointSize() - 1)
        remux_desc.setFont(remux_desc_font)
        proc_form.addRow(remux_desc)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 5)
        self.retry_spin.setValue(self.config.auto_retry)
        retry_hint = QLabel("(0 = no automatic retries)")
        retry_hint.setEnabled(False)
        retry_row = QHBoxLayout()
        retry_row.setSpacing(6)
        retry_row.addWidget(self.retry_spin)
        retry_row.addWidget(retry_hint)
        retry_row.addStretch()
        proc_form.addRow("Auto-retry failed downloads:", retry_row)
        retry_desc = QLabel(
            "How many times a failed download is retried before it is marked as "
            "Failed. Retried items stay in the queue; only a few cases are never "
            "retried automatically (e.g. 404 / video removed / private or invalid "
            "links). Set to 0 to disable and only retry manually."
        )
        retry_desc.setWordWrap(True)
        retry_desc.setEnabled(False)
        retry_font = retry_desc.font()
        retry_font.setPointSize(retry_font.pointSize() - 1)
        retry_desc.setFont(retry_font)
        proc_form.addRow(retry_desc)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.0, 100.0)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setSingleStep(0.5)
        self.speed_spin.setSuffix(" MB/s")
        self.speed_spin.setSpecialValueText("Unlimited")
        self.speed_spin.setValue(self.config.max_download_speed_mbps)
        proc_form.addRow("Max download speed (per agent):", self.speed_spin)

        self.fragments_spin = QSpinBox()
        self.fragments_spin.setRange(0, 32)
        self.fragments_spin.setValue(self.config.concurrent_fragments)
        self.fragments_spin.setSpecialValueText("Default")
        proc_form.addRow("Concurrent HLS fragments:", self.fragments_spin)
        fragments_desc = QLabel(
            "Downloads HLS/DASH video chunks in parallel for faster downloads. "
            "Only affects fragmented (m3u8/DASH) streams; quality, audio and "
            "thumbnails are unchanged."
        )
        fragments_desc.setWordWrap(True)
        fragments_desc.setEnabled(False)
        fragments_desc_font = fragments_desc.font()
        fragments_desc_font.setPointSize(fragments_desc_font.pointSize() - 1)
        fragments_desc.setFont(fragments_desc_font)
        proc_form.addRow(fragments_desc)

        self.downloader_combo = QComboBox()
        self.downloader_combo.addItems(["Native (yt-dlp)", "aria2c"])
        self.downloader_combo.setCurrentIndex(
            1 if self.config.downloader == "aria2c" else 0
        )
        self.downloader_combo.currentIndexChanged.connect(self._on_downloader_changed)
        proc_form.addRow("Downloader:", self.downloader_combo)

        self.aria2c_connections_spin = QSpinBox()
        self.aria2c_connections_spin.setRange(1, 32)
        self.aria2c_connections_spin.setValue(self.config.aria2c_connections)
        proc_form.addRow("aria2c connections per file:", self.aria2c_connections_spin)

        downloader_desc = QLabel(
            "aria2c can speed up direct MP4 downloads with parallel connections; "
            "install it via Tools > aria2c Settings first. HLS/DASH streams always "
            "use fragment downloads."
        )
        downloader_desc.setWordWrap(True)
        downloader_desc.setEnabled(False)
        downloader_desc_font = downloader_desc.font()
        downloader_desc_font.setPointSize(downloader_desc_font.pointSize() - 1)
        downloader_desc.setFont(downloader_desc_font)
        proc_form.addRow(downloader_desc)
        self._on_downloader_changed()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MKV", "WebM"])
        fmt = self.config.preferred_format.lower()
        idx = {"mp4": 0, "mkv": 1, "webm": 2}.get(fmt, 0)
        self.format_combo.setCurrentIndex(idx)
        proc_form.addRow("Video format:", self.format_combo)
        format_desc = QLabel(
            "MP4: prefers a single H.264/AAC file (broadest compatibility), "
            "avoids AV1 unless nothing else is available."
        )
        format_desc.setWordWrap(True)
        format_desc.setEnabled(False)
        format_desc_font = format_desc.font()
        format_desc_font.setPointSize(format_desc_font.pointSize() - 1)
        format_desc.setFont(format_desc_font)
        proc_form.addRow(format_desc)

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

        # Network group
        network_group = QGroupBox("Network")
        network_form = QFormLayout(network_group)
        network_form.setContentsMargins(10, 12, 10, 10)
        network_form.setSpacing(6)

        self.network_indicator_check = QCheckBox("Show network status in the footer")
        self.network_indicator_check.setChecked(self.config.network_indicator_enabled)
        network_form.addRow(self.network_indicator_check)

        self.network_interval_spin = QSpinBox()
        self.network_interval_spin.setRange(5, 600)
        self.network_interval_spin.setSuffix(" s")
        self.network_interval_spin.setValue(self.config.network_poll_interval)
        network_form.addRow("Refresh interval:", self.network_interval_spin)

        layout.addWidget(network_group)

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

    def _on_downloader_changed(self, *_args) -> None:
        is_aria2c = self.downloader_combo.currentIndex() == 1
        self.aria2c_connections_spin.setEnabled(is_aria2c)

    def _save_and_close(self) -> None:
        self.config.set_downloads_dir(self.dir_input.text())
        self.config.set_auto_update(self.auto_update_check.isChecked())
        self.config.set_max_concurrent_downloads(self.concurrent_spin.value())
        self.config.set_remux_to_mp4(self.remux_check.isChecked())
        self.config.set_auto_retry(self.retry_spin.value())
        self.config.set_max_download_speed_mbps(self.speed_spin.value())
        self.config.set_concurrent_fragments(self.fragments_spin.value())
        self.config.set_downloader(
            "aria2c" if self.downloader_combo.currentIndex() == 1 else "native"
        )
        self.config.set_aria2c_connections(self.aria2c_connections_spin.value())
        self.config.set_preferred_format(self.format_combo.currentText().lower())
        res_text = self.resolution_combo.currentText().split()[0].lower().replace("p", "")
        self.config.set_preferred_resolution(f"{res_text}p")
        self.config.set_embed_subs(self.embed_subs_check.isChecked())
        self.config.set_cookies_enabled(self.cookies_enabled_check.isChecked())
        self.config.set_cookies_path(self.cookies_path_input.text())
        self.config.set_network_indicator_enabled(self.network_indicator_check.isChecked())
        self.config.set_network_poll_interval(self.network_interval_spin.value())
        self.accept()
