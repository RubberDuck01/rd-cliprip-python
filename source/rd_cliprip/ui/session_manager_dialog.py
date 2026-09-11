from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPalette
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
from rd_cliprip.ui.row_band import BandDelegate as _BandDelegate, _blend, _rgba
from rd_cliprip.utils import format_dt_short

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
        self.setWindowTitle("RD ClipRip - Session Manager")
        self.setModal(True)
        self.resize(760, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info = QLabel(
            "Each URL list you import becomes its own session with its own "
            "download directory. Pick one to make it active, or create an empty "
            "session to build up by hand."
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
        header_font = self.table.horizontalHeader().font()
        header_font.setBold(False)
        self.table.horizontalHeader().setFont(header_font)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)

        # Row band (hover / selection) behaviour, matching the download queue.
        table = self.table
        highlight = QColor(table.palette().highlight().color())
        window = QColor(table.palette().color(QPalette.ColorRole.Window))
        table._sel_color = QColor(highlight)
        table._hover_fill = _blend(window, highlight, 0.25)
        hover_tint = QColor(highlight)
        hover_tint.setAlpha(55)
        table._hover_color = hover_tint
        table._sel_text = QColor(table.palette().highlightedText().color())
        table._chunk = _blend(highlight, QColor("#ffffff"), 0.35)
        table._hover_row = -1
        table.setItemDelegate(_BandDelegate(table))
        table.viewport().setMouseTracking(True)
        table.viewport().installEventFilter(self)
        table.selectionModel().selectionChanged.connect(self._on_table_selection_changed)

        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, stretch=1)

        self.empty_label = QLabel("No sessions yet. Import a URL list to get started.")
        self.empty_label.setEnabled(False)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        new_empty_btn = QPushButton("New Empty Session")
        new_empty_btn.clicked.connect(self._new_empty)
        btn_row.addWidget(new_empty_btn)
        new_btn = QPushButton("New from .txt...")
        new_btn.clicked.connect(self._new_from_txt)
        btn_row.addWidget(new_btn)
        btn_row.addStretch()
        edit_btn = QPushButton("Edit...")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)
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
        previous = self._selected_id()
        sessions = self.manager.stored_sessions()
        active_id = self.manager.session.id if self.manager.session else None
        self.table._hover_row = -1
        self.table.setRowCount(0)

        for meta in sessions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._append_row(row, meta, meta.get("id") == active_id)

        has_sessions = bool(sessions)
        self.table.setVisible(has_sessions)
        self.empty_label.setVisible(not has_sessions)
        if has_sessions:
            self._select_id(previous if previous else active_id)

    # ------------------------------------------------------------------
    #  Row band behaviour (hover / selection / click-empty deselect)
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.table.viewport():
            event_type = event.type()
            if event_type == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                pos = event.position().toPoint()
                self._set_hover_row(self.table.rowAt(pos.y()))
            elif event_type == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                pos = event.position().toPoint()
                if self.table.rowAt(pos.y()) < 0:
                    self.table.clearSelection()
            elif event_type == QEvent.Type.Leave:
                self._set_hover_row(-1)
        return super().eventFilter(obj, event)

    def _set_hover_row(self, row: int) -> None:
        old = self.table._hover_row
        if row == old:
            return
        self.table._hover_row = row
        self.table.viewport().update()
        self._restyle_bars({old, row})

    def _on_table_selection_changed(self, _selected, _deselected) -> None:
        rows: set[int] = set()
        for index in _selected.indexes():
            rows.add(index.row())
        for index in _deselected.indexes():
            rows.add(index.row())
        self._restyle_bars(rows)

    def _bar_for_row(self, row: int) -> QProgressBar | None:
        host = self.table.cellWidget(row, _COL_PROGRESS)
        if host is None:
            return None
        return host.findChild(QProgressBar)

    def _band_for_row(self, row: int) -> tuple[QColor | None, bool]:
        parent = self.table.model().index(0, 0).parent()
        if self.table.selectionModel().isRowSelected(row, parent):
            return self.table._sel_color, True
        if row == self.table._hover_row:
            return self.table._hover_fill, False
        return None, False

    def _session_bar_css(self, band: QColor | None, selected: bool) -> str:
        chunk = _rgba(self.table._chunk)
        if band is None:
            background = "transparent"
            text = ""
        else:
            background = _rgba(band)
            text = "#ffffff" if (selected or band.lightness() < 128) else "#000000"
        return (
            f"QProgressBar {{ background: {background};"
            f"{f' color: {text};' if text else ''}"
            " text-align: center;"
            " border: 1px solid rgba(120,120,120,110); border-radius: 3px; }"
            f"QProgressBar::chunk {{ background-color: {chunk}; border-radius: 2px; }}"
        )

    def _restyle_bars(self, rows) -> None:
        for row in rows:
            if row < 0 or row >= self.table.rowCount():
                continue
            bar = self._bar_for_row(row)
            if bar is None:
                continue
            band, selected = self._band_for_row(row)
            bar.setStyleSheet(self._session_bar_css(band, selected))

    def _append_row(self, row: int, meta: dict, is_active: bool) -> None:
        label = meta.get("label") or "Untitled"
        source_file = meta.get("source_file") or ""
        created = format_dt_short(meta.get("created_at", ""))

        # Session name
        label_item = QTableWidgetItem(label)
        label_item.setToolTip(
            source_file or label
            + (f"\nCreated: {created}" if created else "")
        )
        if is_active:
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
        host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(4, 5, 4, 5)
        host_layout.addWidget(progress)
        self.table.setCellWidget(row, _COL_PROGRESS, host)
        progress.setStyleSheet(self._session_bar_css(None, False))

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

    def _select_id(self, session_id: str | None) -> None:
        if session_id is None:
            return
        for row, meta in enumerate(self.manager.stored_sessions()):
            if meta.get("id") == session_id:
                self.table.setCurrentCell(row, _COL_LABEL)
                self.table.scrollToItem(self.table.item(row, _COL_LABEL))
                break

    # ------------------------------------------------------------------
    #  Actions
    # ------------------------------------------------------------------

    def _confirm_stop_current(self, session_id: str | None) -> bool:
        """Ask before stopping the running session when the action targets it."""
        if not self.manager.running:
            return True
        current = self.manager.session
        if current is not None and session_id is not None and current.id != session_id:
            return True
        answer = QMessageBox.question(
            self,
            "Downloads in progress",
            "This stops the current downloads (they can be resumed later). "
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _open_selected(self, *_args) -> None:
        session_id = self._selected_id()
        if session_id is None:
            return
        if not self._confirm_stop_current(session_id):
            return
        self.manager.open_session(session_id)
        self._refresh()

    def _edit_selected(self) -> None:
        session_id = self._selected_id()
        if session_id is None:
            return
        if not self._confirm_stop_current(session_id):
            return
        sessions = self.manager.stored_sessions()
        meta = next((s for s in sessions if s.get("id") == session_id), None)
        if meta is None:
            return

        from rd_cliprip.ui.session_edit_dialog import SessionEditDialog

        dialog = SessionEditDialog(
            self,
            label=meta.get("label", "") or "Untitled",
            output_dir=meta.get("output_dir", ""),
        )
        if not dialog.exec():
            return
        label, output_dir = dialog.values()
        self.manager.edit_session(session_id, label=label, output_dir=output_dir)
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

    def _new_empty(self) -> None:
        if not self._confirm_stop_current(None):
            return
        created = self.manager.new_empty_session()
        self._refresh()
        self._select_id(created.id)

    def _new_from_txt(self) -> None:
        # Delegate to the parent window which handles picking + the result popup.
        self.on_new_import()
        self._refresh()
