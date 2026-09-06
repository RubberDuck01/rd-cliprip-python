import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from rd_cliprip.services.updater import RELEASES_PAGE
from rd_cliprip.version import __version__


class UpdateAvailableDialog(QDialog):
    def __init__(self, parent=None, latest_version: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("New Version Available")
        self.setModal(True)
        self.setFixedSize(400, 165)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title_label = QLabel("A new version of RD ClipRip is available!")
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        info_label = QLabel(
            f"Your version: <b>{__version__}</b>&nbsp;&nbsp;→&nbsp;&nbsp;Latest: <b>{latest_version}</b>"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        hint_label = QLabel(f"Do you want to download RD ClipRip {latest_version}?")
        hint_font = hint_label.font()
        hint_font.setPointSize(hint_font.pointSize() - 1)
        hint_label.setFont(hint_font)
        hint_label.setEnabled(False)
        hint_label.setWordWrap(True)
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        download_btn = QPushButton("Yes")
        download_btn.setDefault(True)
        download_btn.clicked.connect(
            lambda: (webbrowser.open(RELEASES_PAGE), self.accept())
        )
        btn_row.addWidget(download_btn)
        later_btn = QPushButton("Later")
        later_btn.clicked.connect(self.reject)
        btn_row.addWidget(later_btn)
        layout.addLayout(btn_row)
