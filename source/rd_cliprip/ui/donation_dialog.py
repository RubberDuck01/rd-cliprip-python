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
    "yt-dlp and FFmpeg. Dozens of developers have poured countless hours into these projects "
    "so that you can enjoy them at no cost.\n\n"
    "If ClipRip saves you time or brings you joy, please consider making a small donation. "
    "Even a coffee's worth makes a real difference and helps keep these projects alive.\n\n"
    "Once you donate, get in touch with me on how to disable this popup for good.\n\n"
    "Thank you for your support!"
)


class DonationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Enjoying RD ClipRip?")
        self.setModal(True)
        self.resize(540, 400)
        self.setFixedSize(540, 400)

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

        # Subtitle
        subtitle_label = QLabel(
            "Please consider supporting the developers who made this possible."
        )
        subtitle_font = subtitle_label.font()
        subtitle_font.setItalic(True)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setEnabled(False)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

        # Body
        body_label = QLabel(_BODY)
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body_label, stretch=1)

        # Donation / support buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        kofi_btn = QPushButton("Donate to Rubber Duck (Ko-fi) \u2665")
        kofi_btn.clicked.connect(
            lambda: webbrowser.open("https://ko-fi.com/rubberduck01")
        )
        btn_row.addWidget(kofi_btn)

        ytdlp_btn = QPushButton("yt-dlp repository")
        ytdlp_btn.clicked.connect(
            lambda: webbrowser.open("https://github.com/yt-dlp/yt-dlp")
        )
        btn_row.addWidget(ytdlp_btn)

        ffmpeg_btn = QPushButton("FFmpeg donations")
        ffmpeg_btn.clicked.connect(
            lambda: webbrowser.open("https://ffmpeg.org/donations.html")
        )
        btn_row.addWidget(ffmpeg_btn)

        layout.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
