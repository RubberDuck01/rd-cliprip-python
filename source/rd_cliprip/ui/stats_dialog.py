from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rd_cliprip.models.session import list_sessions
from rd_cliprip.models.stats import Stats
from rd_cliprip.ui.row_band import band_event_filter, install_row_band
from rd_cliprip.utils import format_dt_short


class StatsDialog(QDialog):
    def __init__(self, parent, stats: Stats) -> None:
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("RD ClipRip - My Statistics")
        self.resize(640, 560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Summary tiles
        tiles = QGridLayout()
        tiles.setSpacing(10)
        self._tile_values: dict[str, QLabel] = {}
        tiles.addWidget(self._tile("downloads", "Videos downloaded", "#2e7d32"), 0, 0)
        tiles.addWidget(self._tile("size", "Total size", "#1565c0"), 0, 1)
        tiles.addWidget(self._tile("duration", "Combined duration", "#b26a00"), 1, 0)
        tiles.addWidget(self._tile("sessions", "Sessions", "#6a1b9a"), 1, 1)
        layout.addLayout(tiles)

        # Timeline
        timeline_group = QGroupBox("Timeline")
        timeline_layout = QHBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(10, 12, 10, 10)
        timeline_layout.setSpacing(10)
        timeline_layout.addWidget(self._info_card("created", "Profile created", "#1565c0"))
        timeline_layout.addWidget(self._info_card("last_run", "Last run", "#2e7d32"))
        layout.addWidget(timeline_group)

        # Session history
        self.sessions_group = QGroupBox("Session history")
        sessions_layout = QVBoxLayout(self.sessions_group)
        sessions_layout.setContentsMargins(10, 12, 10, 10)
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(4)
        self.sessions_table.setHorizontalHeaderLabels(
            ["Session", "Folder", "Progress", "Created"]
        )
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.verticalHeader().setDefaultSectionSize(26)
        header = self.sessions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sessions_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.sessions_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.sessions_table.setAlternatingRowColors(True)
        install_row_band(self.sessions_table)
        self.sessions_table.viewport().installEventFilter(self)
        sessions_layout.addWidget(self.sessions_table)
        layout.addWidget(self.sessions_group, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.reset_btn = QPushButton("Reset Statistics")
        self.reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    # ------------------------------------------------------------------
    #  Building / refresh
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.sessions_table.viewport():
            band_event_filter(self.sessions_table, event)
        return super().eventFilter(obj, event)

    _TILE_STYLE = "QFrame#statTile { background: rgba(128, 128, 128, 28); border-radius: 8px; }"

    def _tile(self, key: str, caption: str, color: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("statTile")
        frame.setStyleSheet(self._TILE_STYLE)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(14, 10, 14, 10)
        frame_layout.setSpacing(2)

        value_label = QLabel("0")
        value_font = value_label.font()
        value_font.setPointSize(value_font.pointSize() + 10)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        caption_label = QLabel(caption)
        caption_label.setEnabled(False)

        frame_layout.addWidget(value_label)
        frame_layout.addWidget(caption_label)
        self._tile_values[key] = value_label
        return frame

    def _info_card(self, key: str, caption: str, color: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("statTile")
        frame.setStyleSheet(self._TILE_STYLE)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(14, 10, 14, 10)
        frame_layout.setSpacing(2)

        caption_label = QLabel(caption)
        caption_label.setEnabled(False)

        value_label = QLabel("N/A")
        value_font = value_label.font()
        value_font.setPointSize(value_font.pointSize() + 2)
        value_font.setBold(True)
        value_label.setFont(value_font)
        value_label.setStyleSheet(f"color: {color};")

        frame_layout.addWidget(caption_label)
        frame_layout.addWidget(value_label)
        self._tile_values[key] = value_label
        return frame

    def _refresh(self) -> None:
        data = self.stats.data
        self._tile_values["downloads"].setText(
            str(data.get("total_files_downloaded", 0))
        )
        self._tile_values["size"].setText(
            self.stats.format_size(float(data.get("total_downloads_size", 0.0)))
        )
        self._tile_values["duration"].setText(
            self.stats.format_duration(int(data.get("total_downloads_duration", 0)))
        )
        self._tile_values["sessions"].setText(str(data.get("total_sessions", 0)))

        self._tile_values["created"].setText(
            format_dt_short(data.get("created_date", "")) or "N/A"
        )
        self._tile_values["last_run"].setText(
            format_dt_short(data.get("last_run_date", "")) or "N/A"
        )
        self._populate_sessions()

    def _populate_sessions(self) -> None:
        sessions = list_sessions()
        self.sessions_table._hover_row = -1
        self.sessions_table.setRowCount(0)
        for meta in sessions:
            row = self.sessions_table.rowCount()
            self.sessions_table.insertRow(row)
            self.sessions_table.setItem(
                row, 0, QTableWidgetItem(meta.get("label") or "Untitled")
            )
            self.sessions_table.setItem(
                row, 1, QTableWidgetItem(meta.get("output_dir", ""))
            )
            total = meta.get("total", 0)
            completed = meta.get("completed", 0)
            remaining = meta.get("remaining", 0)
            progress = f"{completed}/{total}"
            if remaining:
                progress += f"  ({remaining} left)"
            self.sessions_table.setItem(row, 2, QTableWidgetItem(progress))
            self.sessions_table.setItem(
                row, 3, QTableWidgetItem(format_dt_short(meta.get("created_at", "")))
            )
        self.sessions_group.setVisible(bool(sessions))

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset statistics?",
            "This permanently zeroes your download statistics.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.stats.reset()
        self._refresh()
