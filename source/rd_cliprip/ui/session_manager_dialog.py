from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rd_cliprip.controllers.download_manager import DownloadManager

_COL_LABEL = 0
_COL_OUTPUT = 1
_COL_PROGRESS = 2
_COL_CREATED = 3


class SessionManagerDialog(QDialog):
    def __init__(self, parent, manager: DownloadManager, on_new_import) -> None:
        super().__init__(parent)
        self.manager = manager
        self.on_new_import = on_new_import
        self.setWindowTitle("Session Manager")
        self.setModal(True)
        self.resize(720, 420)

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
            ["Session", "Download Folder", "Progress", "Created"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_OUTPUT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COL_CREATED, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, stretch=1)

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

            label = meta.get("label") or "Untitled"
            if meta.get("id") == active_id:
                label += "   (current)"
            label_item = QTableWidgetItem(label)
            label_item.setToolTip(meta.get("source_file") or label)
            self.table.setItem(row, _COL_LABEL, label_item)

            self.table.setItem(
                row, _COL_OUTPUT, QTableWidgetItem(meta.get("output_dir", ""))
            )
            self.table.setItem(
                row,
                _COL_PROGRESS,
                QTableWidgetItem(
                    f"{meta.get('completed', 0)}/{meta.get('total', 0)} done"
                    + (
                        f"  ({meta.get('remaining', 0)} left)"
                        if meta.get("remaining")
                        else ""
                    )
                ),
            )
            created = meta.get("created_at", "")
            try:
                created = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            self.table.setItem(row, _COL_CREATED, QTableWidgetItem(created))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        meta = self.manager.stored_sessions()
        if row >= len(meta):
            return None
        return meta[row].get("id")

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
