import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from rd_cliprip.resources import get_resources_dir

_RESOURCES = get_resources_dir()

_BODY = (
    "RD ClipRip is free and open-source software, and so are the tools that power it — "
    "yt-dlp. Dozens of developers have poured countless hours into these projects "
    "so that you can enjoy them at no cost.\n\n"
    "If ClipRip saves you time or brings you joy, please consider making a small donation. "
    "Even a coffee's worth makes a real difference and helps keep these projects alive.\n\n"
    "Once you donate, get in touch with me on how to disable this popup for good.\n\nThank you for your support!"
)


class DonationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Enjoying RD ClipRip?")
        self.setModal(True)
        self.resize(480, 360)
        self.setFixedSize(480, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Open-source logo
        logo_label = QLabel()
        logo_path = _RESOURCES / "web" / "open-source-logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaledToHeight(
                72, Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pix)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # Title
        title_label = QLabel("This software is free — and it took work to make it.")
        title_font = title_label.font()
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Body
        body_label = QLabel(_BODY)
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        donate_btn = QPushButton("Donate")
        donate_btn.setDefault(True)
        donate_btn.clicked.connect(
            lambda: webbrowser.open("https://buymeacoffee.com/rubberduck")
        )
        btn_row.addWidget(donate_btn)
        later_btn = QPushButton("Maybe Later")
        later_btn.clicked.connect(self.reject)
        btn_row.addWidget(later_btn)
        layout.addLayout(btn_row)
