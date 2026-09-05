from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rd_cliprip.controllers.download_manager import DownloadManager

_COL_LABEL = 0
_COL_OUTPUT = 1
_COL_PROGRESS = 2
_COL_STATUS = 3

_COLOR_ACTIVE = QColor("#1565c0")
_COLOR_REMAINING = QColor("#b26a00")
_COLOR_DONE = QColor("#2e7d32")
_COLOR_EMPTY = QColor("#9e9e9e")


class SessionManagerDialog(QDialog):
    def __init__(self, parent, manager: DownloadManager, on_new_import) -> None:
        super().__init__(parent)
        self.manager = manager
        self.on_new_import = on_new_import
        self.setWindowTitle("Session Manager")
        self.setModal(True)
        self.resize(760, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info = QLabel(
            "Each URL list you import becomes its own session with its own "
            "download folder. Pick one to make it active."
        )
        info.setWordWrap(True)
        info.setEnabled(False)
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Session", "Download Folder", "Progress", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_OUTPUT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(_COL_PROGRESS, 170)
        self.table.setColumnWidth(_COL_STATUS, 150)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, stretch=1)

        self.empty_label = QLabel("No sessions yet. Import a URL list to get started.")
        self.empty_label.setEnabled(False)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        new_btn = QPushButton("New from .txt...")
        new_btn.clicked.connect(self._new_from_txt)
        btn_row.addWidget(new_btn)
        btn_row.addStretch()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(open_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    # ------------------------------------------------------------------
    #  Population
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        sessions = self.manager.stored_sessions()
        active_id = self.manager.session.id if self.manager.session else None
        self.table.setRowCount(0)

        for meta in sessions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._append_row(row, meta, meta.get("id") == active_id)

        has_sessions = bool(sessions)
        self.table.setVisible(has_sessions)
        self.empty_label.setVisible(not has_sessions)

    def _append_row(self, row: int, meta: dict, is_active: bool) -> None:
        label = meta.get("label") or "Untitled"
        source_file = meta.get("source_file") or ""
        created = meta.get("created_at", "")
        try:
            created = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

        # Session name
        label_item = QTableWidgetItem(label)
        label_item.setToolTip(
            source_file or label
            + (f"\nCreated: {created}" if created else "")
        )
        if is_active:
            font = QFont(label_item.font())
            font.setBold(True)
            label_item.setFont(font)
            label_item.setForeground(_COLOR_ACTIVE)
        self.table.setItem(row, _COL_LABEL, label_item)

        # Download folder
        folder_item = QTableWidgetItem(meta.get("output_dir", ""))
        folder_item.setToolTip(
            meta.get("output_dir", "")
            + (f"\nSource: {source_file}" if source_file else "")
        )
        self.table.setItem(row, _COL_OUTPUT, folder_item)

        # Progress bar (same look as the download queue)
        total = meta.get("total", 0)
        done = meta.get("completed", 0)
        remaining = meta.get("remaining", 0)

        progress = QProgressBar()
        progress.setTextVisible(True)
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(min(done, total))
            progress.setFormat(f"{done}/{total}")
            progress.setToolTip(f"{done} of {total} done")
        else:
            progress.setRange(0, 1)
            progress.setValue(0)
            progress.setFormat("\u2014")

        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(4, 5, 4, 5)
        host_layout.addWidget(progress)
        self.table.setCellWidget(row, _COL_PROGRESS, host)

        # Status column
        if total == 0:
            status = "Empty"
            color = _COLOR_EMPTY
        elif remaining == 0:
            status = "Complete"
            color = _COLOR_DONE
        elif is_active:
            status = f"{remaining} left  \u00b7 active"
            color = _COLOR_ACTIVE
        else:
            status = f"{remaining} left"
            color = _COLOR_REMAINING
        status_item = QTableWidgetItem(status)
        status_item.setForeground(color)
        self.table.setItem(row, _COL_STATUS, status_item)

    # ------------------------------------------------------------------
    #  Selection helpers
    # ------------------------------------------------------------------

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        sessions = self.manager.stored_sessions()
        if row >= len(sessions):
            return None
        return sessions[row].get("id")

    # ------------------------------------------------------------------
    #  Actions
    # ------------------------------------------------------------------

    def _open_selected(self, *_args) -> None:
        session_id = self._selected_id()
        if session_id is None:
            return
        if self.manager.running:
            answer = QMessageBox.question(
                self,
                "Downloads in progress",
                "Opening another session stops the current downloads "
                "(they can be resumed later). Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.manager.open_session(session_id)
        self._refresh()

    def _delete_selected(self) -> None:
        session_id = self._selected_id()
        if session_id is None:
            return
        is_current = self.manager.session is not None and self.manager.session.id == session_id
        extra = "\n\nThis is the active session." if is_current else ""
        answer = QMessageBox.question(
            self,
            "Delete session?",
            f"Delete this session and all its progress?{extra}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.delete_session(session_id)
        self._refresh()

    def _new_from_txt(self) -> None:
        # Delegate to the parent window which handles picking + the result popup.
        self.on_new_import()
        self._refresh()
