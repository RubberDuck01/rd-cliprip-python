from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from rd_cliprip.models.stats import Stats
from rd_cliprip.utils import format_dt_short


class StatsDialog(QDialog):
    def __init__(self, parent, stats: Stats) -> None:
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("RD ClipRip - My Statistics")
        self.resize(400, 280)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Usage stats group
        stats_group = QGroupBox("Usage Statistics")
        stats_form = QFormLayout(stats_group)
        stats_form.setContentsMargins(10, 12, 10, 10)
        stats_form.setSpacing(6)
        stats_form.addRow("Sessions:", QLabel(str(self.stats.data.get("total_sessions", 0))))
        stats_form.addRow("Videos downloaded:", QLabel(str(self.stats.data.get("total_files_downloaded", 0))))
        stats_form.addRow("Total size:", QLabel(self.stats.data.get("total_downloads_size_pretty", "0 B")))
        stats_form.addRow(
            "Total duration (combined):",
            QLabel(self.stats.data.get("total_downloads_duration_pretty", "00:00")),
        )
        layout.addWidget(stats_group)

        # Timeline group
        timeline_group = QGroupBox("Timeline")
        timeline_form = QFormLayout(timeline_group)
        timeline_form.setContentsMargins(10, 12, 10, 10)
        timeline_form.setSpacing(6)
        timeline_form.addRow(
            "Last run:",
            QLabel(format_dt_short(self.stats.data.get("last_run_date", "")) or "N/A"),
        )
        timeline_form.addRow(
            "Profile created:",
            QLabel(format_dt_short(self.stats.data.get("created_date", "")) or "N/A"),
        )
        layout.addWidget(timeline_group)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
