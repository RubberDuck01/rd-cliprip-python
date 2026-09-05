from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rd_cliprip.models.session import (
    STATE_ACTIVE,
    STATE_CANCELLED,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_QUEUED,
    SessionItem,
)

_COL_INDEX = 0
_COL_ITEM = 1
_COL_PROGRESS = 2
_COL_STATUS = 3

_COLORS = {
    STATE_COMPLETED: QColor("#2e7d32"),
    STATE_FAILED: QColor("#c62828"),
    STATE_ACTIVE: QColor("#1565c0"),
    STATE_CANCELLED: QColor("#9e9e9e"),
    STATE_QUEUED: QColor("#555555"),
}


class DownloadsTable(QTableWidget):
    retry_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)
    open_folder_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._row_for_id: dict[str, int] = {}
        self._state_for_id: dict[str, str] = {}
        self._dest_for_id: dict[str, list[str]] = {}
        self._progress_for_id: dict[str, QProgressBar] = {}

        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["#", "Item", "Progress", "Status"])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)

        header = self.horizontalHeader()
        # '#' fixed and tiny; 'Item' takes the free space; 'Status' is user-resizable.
        header.setSectionResizeMode(_COL_INDEX, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_ITEM, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(_COL_INDEX, 40)
        self.setColumnWidth(_COL_PROGRESS, 180)
        self.setColumnWidth(_COL_STATUS, 220)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    #  Rendering
    # ------------------------------------------------------------------

    def refresh_items(self, items: list[SessionItem]) -> None:
        self.setRowCount(0)
        self._row_for_id.clear()
        self._state_for_id.clear()
        self._dest_for_id.clear()
        self._progress_for_id.clear()
        for index, item in enumerate(items):
            self._append_row(index, item)

    def _append_row(self, display_index: int, item: SessionItem) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self._row_for_id[item.id] = row
        self._state_for_id[item.id] = item.state
        self._dest_for_id[item.id] = item.dest_paths

        num_item = QTableWidgetItem(str(display_index + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, _COL_INDEX, num_item)

        item_item = QTableWidgetItem(item.title or item.url)
        item_item.setToolTip(item.url)
        self.setItem(row, _COL_ITEM, item_item)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(True)
        progress.setValue(max(0, min(100, item.progress)))
        # Center the bar vertically inside the row and keep it off the cell edges.
        progress_host = QWidget()
        host_layout = QVBoxLayout(progress_host)
        host_layout.setContentsMargins(4, 5, 4, 5)
        host_layout.addWidget(progress)
        self.setCellWidget(row, _COL_PROGRESS, progress_host)
        self._progress_for_id[item.id] = progress

        status_item = QTableWidgetItem(self._status_text(item))
        status_item.setToolTip(item.error or "")
        self.setItem(row, _COL_STATUS, status_item)

        self._color_row(row, item.state)

    def update_item(self, item: SessionItem) -> None:
        row = self._row_for_id.get(item.id)
        if row is None:
            return
        self._state_for_id[item.id] = item.state
        self._dest_for_id[item.id] = item.dest_paths

        widget = self._progress_for_id.get(item.id)
        if isinstance(widget, QProgressBar):
            widget.setValue(max(0, min(100, item.progress)))

        status_item = self.item(row, _COL_STATUS)
        if status_item is not None:
            status_item.setText(self._status_text(item))
            status_item.setToolTip(item.error or "")

        item_cell = self.item(row, _COL_ITEM)
        if item_cell is not None and item.title:
            item_cell.setText(item.title)
            item_cell.setToolTip(item.url or item.title)

        self._color_row(row, item.state)

    def remove_item(self, item_id: str) -> None:
        row = self._row_for_id.pop(item_id, None)
        self._state_for_id.pop(item_id, None)
        self._dest_for_id.pop(item_id, None)
        self._progress_for_id.pop(item_id, None)
        if row is not None:
            self.removeRow(row)
            self._reindex()

    def _reindex(self) -> None:
        self._row_for_id = {item_id: r for r, item_id in enumerate(self._row_for_id)}
        for row in range(self.rowCount()):
            num_item = self.item(row, _COL_INDEX)
            if num_item is not None:
                num_item.setText(str(row + 1))

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _color_row(self, row: int, state: str) -> None:
        item = self.item(row, _COL_INDEX)
        if item is not None:
            item.setForeground(_COLORS.get(state, _COLORS[STATE_QUEUED]))

    @staticmethod
    def _status_text(item: SessionItem) -> str:
        if item.state == STATE_COMPLETED:
            count = len(item.dest_paths)
            return f"Saved ({count} file{'s' if count != 1 else ''})"
        if item.state == STATE_ACTIVE:
            return f"Downloading\u2026 {item.progress}%"
        if item.state == STATE_FAILED:
            short = (item.error or "Failed").replace("\n", " ")
            return f"Failed \u2014 {short[:60]}"
        if item.state == STATE_CANCELLED:
            return "Cancelled"
        return "Queued"

    # ------------------------------------------------------------------
    #  Context menu
    # ------------------------------------------------------------------

    def item_id_at(self, row: int) -> str | None:
        for item_id, r in self._row_for_id.items():
            if r == row:
                return item_id
        return None

    def item_state(self, item_id: str) -> str:
        return self._state_for_id.get(item_id, STATE_QUEUED)

    def item_dest_paths(self, item_id: str) -> list[str]:
        return self._dest_for_id.get(item_id, [])

    def _show_context_menu(self, pos) -> None:
        row = self.rowAt(pos.y())
        if row < 0:
            return
        item_id = self.item_id_at(row)
        if item_id is None:
            return
        state = self.item_state(item_id)

        menu = QMenu(self)
        retry_action = menu.addAction("Retry")
        cancel_action = menu.addAction("Cancel")
        open_action = menu.addAction("Open Folder")
        menu.addSeparator()
        remove_action = menu.addAction("Remove from List")

        retry_action.setEnabled(state in (STATE_FAILED, STATE_CANCELLED))
        cancel_action.setEnabled(state == STATE_ACTIVE)
        open_action.setEnabled(bool(self.item_dest_paths(item_id)))

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is retry_action:
            self.retry_requested.emit(item_id)
        elif chosen is cancel_action:
            self.cancel_requested.emit(item_id)
        elif chosen is open_action:
            self.open_folder_requested.emit(item_id)
        elif chosen is remove_action:
            self.remove_requested.emit(item_id)
