from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
_COL_SPEED = 3
_COL_ETA = 4
_COL_SIZE = 5
_COL_STATUS = 6

_DASH = "-"

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
    open_file_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._row_for_id: dict[str, int] = {}
        self._state_for_id: dict[str, str] = {}
        self._dest_for_id: dict[str, list[str]] = {}
        self._url_for_id: dict[str, str] = {}
        self._progress_for_id: dict[str, QProgressBar] = {}

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(
            ["#", "Video", "Progress", "Speed", "ETA", "Size", "Status"]
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)

        header = self.horizontalHeader()
        # Every column except '#' is user-resizable.
        header.setSectionResizeMode(_COL_INDEX, QHeaderView.ResizeMode.Fixed)
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(40)
        self.setColumnWidth(_COL_INDEX, 36)
        self.setColumnWidth(_COL_ITEM, 320)
        self.setColumnWidth(_COL_PROGRESS, 160)
        self.setColumnWidth(_COL_SPEED, 95)
        self.setColumnWidth(_COL_ETA, 80)
        self.setColumnWidth(_COL_SIZE, 90)
        self.setColumnWidth(_COL_STATUS, 110)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_clicked)

    # ------------------------------------------------------------------
    #  Rendering
    # ------------------------------------------------------------------

    def refresh_items(self, items: list[SessionItem]) -> None:
        self.setRowCount(0)
        self._row_for_id.clear()
        self._state_for_id.clear()
        self._dest_for_id.clear()
        self._url_for_id.clear()
        self._progress_for_id.clear()
        for index, item in enumerate(items):
            self._append_row(index, item)

    def _append_row(self, display_index: int, item: SessionItem) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self._row_for_id[item.id] = row
        self._state_for_id[item.id] = item.state
        self._dest_for_id[item.id] = item.dest_paths
        self._url_for_id[item.id] = item.url

        num_item = QTableWidgetItem(str(display_index + 1))
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, _COL_INDEX, num_item)

        name_item = QTableWidgetItem(item.title or item.url)
        name_item.setToolTip(item.url)
        self.setItem(row, _COL_ITEM, name_item)

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

        self.setItem(row, _COL_SPEED, QTableWidgetItem(_DASH))
        self.setItem(row, _COL_ETA, QTableWidgetItem(_DASH))
        self.setItem(row, _COL_SIZE, self._size_cell(item))
        self._set_cells_align(row)

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

        if item.state == STATE_COMPLETED:
            self.setItem(row, _COL_SPEED, QTableWidgetItem(_DASH))
            self.setItem(row, _COL_ETA, QTableWidgetItem(_DASH))
            self.setItem(row, _COL_SIZE, self._size_cell(item))
            self._set_cells_align(row)

        name_cell = self.item(row, _COL_ITEM)
        if name_cell is not None and item.title:
            name_cell.setText(item.title)
            name_cell.setToolTip(item.url or item.title)

        self._color_row(row, item.state)

    def update_progress(
        self, item_id: str, percent: int, speed: str, eta: str, total: str
    ) -> None:
        """Refresh the live Speed / ETA / Size columns for an active row."""
        row = self._row_for_id.get(item_id)
        if row is None:
            return
        widget = self._progress_for_id.get(item_id)
        if isinstance(widget, QProgressBar):
            widget.setValue(max(0, min(100, percent)))

        speed_item = self.item(row, _COL_SPEED)
        if speed_item is not None:
            speed_item.setText(speed or _DASH)

        eta_item = self.item(row, _COL_ETA)
        if eta_item is not None:
            eta_item.setText(eta or _DASH)

        size_item = self.item(row, _COL_SIZE)
        if size_item is not None:
            size_item.setText(total or _DASH)

        status_item = self.item(row, _COL_STATUS)
        if status_item is not None and self.item_state(item_id) == STATE_ACTIVE:
            status_item.setText(f"Downloading\u2026 {percent}%")

    def remove_item(self, item_id: str) -> None:
        row = self._row_for_id.pop(item_id, None)
        self._state_for_id.pop(item_id, None)
        self._dest_for_id.pop(item_id, None)
        self._url_for_id.pop(item_id, None)
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

    def _set_cells_align(self, row: int) -> None:
        for col in (_COL_SPEED, _COL_ETA, _COL_SIZE):
            item = self.item(row, col)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _size_cell(item: SessionItem) -> QTableWidgetItem:
        cell = QTableWidgetItem(
            DownloadsTable._completed_size(item.size_mb) if item.state == STATE_COMPLETED else _DASH
        )
        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return cell

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

    def item_url(self, item_id: str) -> str:
        return self._url_for_id.get(item_id, "")

    def _copy_url(self, item_id: str) -> None:
        url = self.item_url(item_id)
        if url:
            QApplication.clipboard().setText(url)

    def _on_double_clicked(self, row: int, _col: int) -> None:
        item_id = self.item_id_at(row)
        if item_id is None:
            return
        if self.item_state(item_id) == STATE_COMPLETED and self.item_dest_paths(item_id):
            self.open_file_requested.emit(item_id)

    def _show_context_menu(self, pos) -> None:
        row = self.rowAt(pos.y())
        if row < 0:
            return
        item_id = self.item_id_at(row)
        if item_id is None:
            return
        state = self.item_state(item_id)
        has_file = bool(self.item_dest_paths(item_id))

        menu = QMenu(self)
        retry_action = menu.addAction("Retry")
        cancel_action = menu.addAction("Cancel")
        menu.addSeparator()
        copy_action = menu.addAction("Copy URL")
        open_file_action = menu.addAction("Open File")
        open_folder_action = menu.addAction("Open Folder")
        menu.addSeparator()
        remove_action = menu.addAction("Remove from List")

        retry_action.setEnabled(state in (STATE_FAILED, STATE_CANCELLED))
        cancel_action.setEnabled(state == STATE_ACTIVE)
        open_file_action.setEnabled(has_file)
        open_folder_action.setEnabled(has_file)

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is retry_action:
            self.retry_requested.emit(item_id)
        elif chosen is cancel_action:
            self.cancel_requested.emit(item_id)
        elif chosen is copy_action:
            self._copy_url(item_id)
        elif chosen is open_file_action:
            self.open_file_requested.emit(item_id)
        elif chosen is open_folder_action:
            self.open_folder_requested.emit(item_id)
        elif chosen is remove_action:
            self.remove_requested.emit(item_id)
