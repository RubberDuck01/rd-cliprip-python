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
        self.setWindowTitle("RD ClipRip - About")
        self.setModal(True)
        self.resize(480, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Icon + app name row
        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._icon_label = QLabel()
        icon_path = _RESOURCES / "rd" / "rd-cliprip-logo.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_label.setPixmap(pix)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_label.mousePressEvent = self._on_icon_clicked
        header_row.addWidget(self._icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name_label = QLabel("RD ClipRip")
        name_font = name_label.font()
        name_font.setPointSize(name_font.pointSize() + 6)
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)

        version_label = QLabel(f"Version {__version__}")
        version_label.setEnabled(False)
        info_layout.addWidget(version_label)

        desc_label = QLabel("Powerful video downloader — Made with \u2665 by Rubber Duck")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)

        info_layout.addSpacing(8)

        powered_label = QLabel("Powered by yt-dlp and PyQt6")
        powered_label.setEnabled(False)
        info_layout.addWidget(powered_label)

        header_row.addLayout(info_layout, stretch=1)
        layout.addLayout(header_row)

        # Donation checkbox (hidden until 13 clicks)
        self._donation_check = QCheckBox("I have donated (enable to dismiss the donation popup)")
        self._donation_check.setVisible(False)
        if self.config:
            self._donation_check.setChecked(self.config.i_have_donated)
            self._donation_check.toggled.connect(lambda checked: self.config.set_i_have_donated(checked))
        layout.addWidget(self._donation_check)

        # License text
        license_label = QLabel(_UNLICENSE)
        license_label.setWordWrap(True)
        license_label.setEnabled(False)
        license_font = license_label.font()
        license_font.setPointSize(license_font.pointSize() - 1)
        license_label.setFont(license_font)
        layout.addWidget(license_label, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        github_btn = QPushButton("View Source on GitHub")
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
        if self._icon_clicks >= self._CLICKS_REQUIRED:
            self._donation_check.setVisible(True)
