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
_COL_DETAILS = 3
_COL_STATUS = 4

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
        self._details_for_id: dict[str, tuple[str, str, str]] = {}

        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(
            ["#", "Item", "Progress", "Speed / ETA / Size", "Status"]
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)

        header = self.horizontalHeader()
        # '#' fixed and tiny; 'Item' takes the free space; the other two are
        # user-resizable so people can widen Speed/ETA or Status as needed.
        header.setSectionResizeMode(_COL_INDEX, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_ITEM, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_DETAILS, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(_COL_INDEX, 40)
        self.setColumnWidth(_COL_PROGRESS, 180)
        self.setColumnWidth(_COL_DETAILS, 240)
        self.setColumnWidth(_COL_STATUS, 180)

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
        self._details_for_id.clear()
        for index, item in enumerate(items):
            self._append_row(index, item)

    def _append_row(self, display_index: int, item: SessionItem) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self._row_for_id[item.id] = row
        self._state_for_id[item.id] = item.state
        self._dest_for_id[item.id] = item.dest_paths
        self._details_for_id[item.id] = ("", "", "")

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

        details_item = QTableWidgetItem("")
        details_item.setToolTip("")
        self.setItem(row, _COL_DETAILS, details_item)

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

        # Completed rows show the final file size; others keep live data.
        details_item = self.item(row, _COL_DETAILS)
        if details_item is not None:
            if item.state == STATE_COMPLETED:
                details_item.setText(self._completed_size(item.size_mb))
                details_item.setToolTip(self._completed_size(item.size_mb))
            elif item.state not in (STATE_ACTIVE,):
                speed, eta, total = self._details_for_id.get(item.id, ("", "", ""))
                if not (speed or eta or total):
                    details_item.setText("")

        item_cell = self.item(row, _COL_ITEM)
        if item_cell is not None and item.title:
            item_cell.setText(item.title)
            item_cell.setToolTip(item.url or item.title)

        self._color_row(row, item.state)

    def update_progress(self, item_id: str, percent: int, speed: str, eta: str, total: str) -> None:
        """Refresh the live Speed/ETA/Size + progress for an active row."""
        row = self._row_for_id.get(item_id)
        if row is None:
            return
        widget = self._progress_for_id.get(item_id)
        if isinstance(widget, QProgressBar):
            widget.setValue(max(0, min(100, percent)))

        self._details_for_id[item_id] = (speed, eta, total)
        details_item = self.item(row, _COL_DETAILS)
        if details_item is not None:
            text = self._live_details(speed, eta, total)
            details_item.setText(text)
            details_item.setToolTip(text)

        status_item = self.item(row, _COL_STATUS)
        if status_item is not None and self.item_state(item_id) == STATE_ACTIVE:
            status_item.setText(f"Downloading\u2026 {percent}%")

    def remove_item(self, item_id: str) -> None:
        row = self._row_for_id.pop(item_id, None)
        self._state_for_id.pop(item_id, None)
        self._dest_for_id.pop(item_id, None)
        self._progress_for_id.pop(item_id, None)
        self._details_for_id.pop(item_id, None)
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

    @staticmethod
    def _live_details(speed: str, eta: str, total: str) -> str:
        parts: list[str] = []
        if speed:
            parts.append(speed)
        if eta:
            parts.append("ETA " + eta)
        if total:
            parts.append("of " + total)
        return "  \u00b7  ".join(parts)

    @staticmethod
    def _completed_size(size_mb: float) -> str:
        try:
            mb = max(0.0, float(size_mb))
        except (TypeError, ValueError):
            return ""
        if mb <= 0:
            return ""
        if mb >= 1024:
            return f"{mb / 1024:.2f} GiB"
        return f"{mb:.2f} MiB"

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
