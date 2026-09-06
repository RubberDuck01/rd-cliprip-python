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
    get_aria2c_version,
    get_tools_aria2c_path,
    install_or_update_aria2c,
)


class Aria2cDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RD ClipRip - aria2c Settings")
        self.setModal(True)
        self.resize(500, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        status_group = QGroupBox("aria2c Status")
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
        status_form.addRow("Installed in:", QLabel(str(get_tools_aria2c_path())))
        layout.addWidget(status_group)

        hint = QLabel(
            "aria2c is an optional faster downloader for direct/single-file "
            "downloads (e.g. large MP4s). Select 'aria2c' in Settings to use it; "
            "HLS streams still use fragment downloads regardless."
        )
        hint.setWordWrap(True)
        hint.setEnabled(False)
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.refresh_btn = QPushButton("Refresh")
        self.install_update_btn = QPushButton("Install / Update")
        action_row.addWidget(self.refresh_btn)
        action_row.addWidget(self.install_update_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        layout.addStretch()

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        self.refresh_btn.clicked.connect(self.refresh_status)
        self.install_update_btn.clicked.connect(self.install_or_update)

        self.refresh_status()

    def refresh_status(self) -> None:
        installed = get_tools_aria2c_path().exists()
        self.install_status_value.setText(
            "Installed!" if installed else "Not installed, use the Install / Update button."
        )
        version = get_aria2c_version()
        self.version_value.setText(version if version else "Not installed")
        self.install_update_btn.setText("Update" if installed else "Install")

    def install_or_update(self) -> None:
        self.install_update_btn.setEnabled(False)
        self.install_update_btn.setText("Working...")
        try:
            ok, message = install_or_update_aria2c()
        finally:
            self.refresh_status()
        if ok:
            QMessageBox.information(
                self, "RD ClipRip - aria2c Settings", "aria2c install/update completed."
            )
        else:
            QMessageBox.critical(self, "RD ClipRip - aria2c Settings", message)
