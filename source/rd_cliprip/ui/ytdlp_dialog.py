from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from rd_cliprip.services.downloader import (
    get_tools_ytdlp_path,
    get_ytdlp_version,
    install_ytdlp,
    update_ytdlp,
)


class YtdlpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RD ClipRip - yt-dlp Settings")
        self.setModal(True)
        self.resize(500, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Status group
        status_group = QGroupBox("yt-dlp Status")
        status_form = QFormLayout(status_group)
        status_form.setContentsMargins(10, 12, 10, 10)
        status_form.setSpacing(6)

        self.install_status_value = QLabel("Checking...")
        self.version_value = QLabel("Checking...")
        self.version_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        status_form.addRow("Installed:", self.install_status_value)
        status_form.addRow("Version:", self.version_value)
        status_form.addRow("Installed in:", QLabel(str(get_tools_ytdlp_path())))
        layout.addWidget(status_group)

        # Actions
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.refresh_btn = QPushButton("Refresh")
        self.install_btn = QPushButton("Install")
        self.update_btn = QPushButton("Update")
        action_row.addWidget(self.refresh_btn)
        action_row.addWidget(self.install_btn)
        action_row.addWidget(self.update_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        layout.addStretch()

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        self.refresh_btn.clicked.connect(self.refresh_version)
        self.install_btn.clicked.connect(self.install_yt_dlp)
        self.update_btn.clicked.connect(self.update_yt_dlp)
        close_btn.clicked.connect(self.accept)

        self.refresh_version()

    def refresh_version(self) -> None:
        target_installed = get_tools_ytdlp_path().exists()
        self.install_status_value.setText(
            "Installed!" if target_installed else "Not installed, use the Install button."
        )
        version = get_ytdlp_version()
        self.version_value.setText(version if version else "Not installed")
        self.update_btn.setEnabled(target_installed)

    def install_yt_dlp(self) -> None:
        if get_tools_ytdlp_path().exists():
            QMessageBox.information(
                self,
                "RD ClipRip - yt-dlp Settings",
                "yt-dlp is already installed, nothing to do.",
            )
            self.refresh_version()
            return

        ok, message = install_ytdlp()
        self.refresh_version()
        if ok:
            QMessageBox.information(
                self, "RD ClipRip - yt-dlp Settings", "yt-dlp installation completed!"
            )
        else:
            QMessageBox.critical(self, "RD ClipRip - yt-dlp Settings", message)

    def update_yt_dlp(self) -> None:
        ok, message = update_ytdlp()
        self.refresh_version()
        if ok:
            QMessageBox.information(self, "RD ClipRip - yt-dlp Settings", "Done!")
        else:
            QMessageBox.critical(self, "RD ClipRip - yt-dlp Settings", message)
