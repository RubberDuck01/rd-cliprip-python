import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rd_cliprip.models.config import Config
from rd_cliprip.resources import get_resources_dir
from rd_cliprip.version import __version__

_RESOURCES = get_resources_dir()

_UNLICENSE = (
    "This is free and unencumbered software released into the public domain.\n\n"
    "Anyone is free to copy, modify, publish, use, compile, sell, or distribute "
    "this software, either in source code form or as compiled binaries, for any "
    "purpose, commercial or non-commercial, and by any means.\n\n"
    "In jurisdictions that recognize copyright laws, the author or authors of this "
    "software dedicate any and all copyright interest in the software to the public "
    "domain. We make this dedication for the benefit of the public at large and to "
    "the detriment of our heirs and successors. We intend this dedication to be an "
    "overt act of relinquishment in perpetuity of all present and future rights to "
    "this software under copyright law.\n\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR '
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
    "AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN "
    "ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION "
    "WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n\n"
    "For more information, please refer to <https://unlicense.org>"
)


class AboutDialog(QDialog):
    _CLICKS_REQUIRED = 13

    def __init__(self, parent=None, config: Config | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._icon_clicks = 0
        self.setWindowTitle("Rubber Duck's ClipRip - About")
        self.setModal(True)
        self.resize(560, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Icon + app name row (logo shown big and proud)
        header_row = QHBoxLayout()
        header_row.setSpacing(20)
        header_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._icon_label = QLabel()
        icon_path = _RESOURCES / "rd" / "rd-cliprip-logo.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                140,
                140,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_label.setPixmap(pix)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_label.mousePressEvent = self._on_icon_clicked
        header_row.addWidget(self._icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        name_label = QLabel("RD ClipRip")
        name_font = name_label.font()
        name_font.setPointSize(name_font.pointSize() + 5)
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)

        desc_label = QLabel(
            "The EZ video downloader.\nBuilt with Python and Qt6, powered by yt-dlp."
        )
        info_layout.addWidget(desc_label)

        version_label = QLabel(f"Version: {__version__}")
        version_font = version_label.font()
        version_font.setItalic(True)
        version_label.setFont(version_font)
        version_label.setEnabled(False)
        info_layout.addWidget(version_label)

        header_row.addLayout(info_layout)
        header_row.addStretch()
        layout.addLayout(header_row)

        # License text (same readable text box as AudioRip)
        license_edit = QTextEdit()
        license_edit.setReadOnly(True)
        license_edit.setPlainText(_UNLICENSE)
        layout.addWidget(license_edit, stretch=1)

        # Hidden donation opt-out section (revealed after 13 icon clicks)
        self._donation_section = QWidget()
        don_layout = QVBoxLayout(self._donation_section)
        don_layout.setContentsMargins(0, 4, 0, 0)
        don_layout.setSpacing(4)

        don_hint = QLabel(
            "Be honest and only tick this option if you have actually donated.\n"
            "It will permanently silence the donation popup that appears on exit.\n\n"
            "If you found this by mashing the logo, you clearly enjoy the app - "
            "but a small donation helps keep ClipRip alive. Pretty please? ;)"
        )
        don_hint_font = don_hint.font()
        don_hint_font.setItalic(True)
        don_hint_font.setPointSize(don_hint_font.pointSize() - 1)
        don_hint.setFont(don_hint_font)
        don_hint.setEnabled(False)
        don_hint.setWordWrap(True)
        don_layout.addWidget(don_hint)

        self._donated_check = QCheckBox("I have donated (and I promise I'm not a liar)")
        if self.config is not None:
            self._donated_check.setChecked(self.config.i_have_donated)
        self._donated_check.toggled.connect(self._on_donated_toggled)
        don_layout.addWidget(self._donated_check)

        self._donation_section.setVisible(False)
        layout.addWidget(self._donation_section)

        # Buttons
        btn_row = QHBoxLayout()
        github_btn = QPushButton("Source Code (GitHub)")
        github_btn.clicked.connect(
            lambda: webbrowser.open("https://github.com/RubberDuck01/rd-cliprip-python")
        )
        btn_row.addWidget(github_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_icon_clicked(self, event) -> None:
        self._icon_clicks += 1
        remaining = self._CLICKS_REQUIRED - self._icon_clicks
        if remaining > 0:
            self._icon_label.setToolTip(
                f"{remaining} more click{'s' if remaining != 1 else ''}..."
            )
        else:
            self._icon_label.setToolTip("")
            self._donation_section.setVisible(True)

    def _on_donated_toggled(self, checked: bool) -> None:
        if self.config is not None:
            self.config.set_i_have_donated(checked)
