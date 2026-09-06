from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPalette, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QMenu,
    QProgressBar,
    QStyle,
    QStyledItemDelegate,
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

_BAR_FILL = {
    STATE_COMPLETED: "#2e7d32",
    STATE_FAILED: "#c62828",
    STATE_ACTIVE: "#1565c0",
}

_DASH_COLOR = QColor("#8a8a8a")


def _blend(c1: QColor, c2: QColor, t: float) -> QColor:
    """Mix c1 into c2; t=0 is c1, t=1 is c2."""
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


def _rgba(color: QColor) -> str:
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"


class _BandDelegate(QStyledItemDelegate):
    """Paint selection / hover as one plain band per row (qBittorrent-like).

    Qt's built-in style draws each selected cell as its own rounded tile.
    This delegate instead fills the cell with a plain rectangle (adjacent cells
    merge into a single continuous row band) and never lets the style paint a
    per-cell selection/focus bubble.
    """

    def __init__(self, table) -> None:
        super().__init__(table)
        self._table = table

    def paint(self, painter, option, index) -> None:
        row = index.row()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = not selected and row == self._table._hover_row

        if selected:
            painter.fillRect(option.rect, self._table._sel_color)
        elif hovered:
            painter.fillRect(option.rect, self._table._hover_color)

        # Draw the text ourselves with an explicitly normal-weight font so
        # selection can never make it bold.
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is None:
            text = ""
        font = QFont(option.font)
        font.setBold(False)
        painter.setFont(font)

        if selected:
            color = self._table._sel_text
        else:
            fg = index.data(Qt.ItemDataRole.ForegroundRole)
            color = (
                fg.color()
                if isinstance(fg, QBrush)
                else QColor(option.palette.color(QPalette.ColorRole.Text))
            )
        painter.setPen(QPen(color))

        align_data = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if align_data is not None:
            alignment = int(align_data)
        else:
            alignment = int(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        rect = option.rect.adjusted(4, 0, -4, 0)
        elided = painter.fontMetrics().elidedText(
            str(text), Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.drawText(rect, alignment, elided)


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
        header_font = self.horizontalHeader().font()
        header_font.setBold(False)
        self.horizontalHeader().setFont(header_font)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(_BandDelegate(self))

        # qBittorrent-style: hovering highlights the whole row, not one cell.
        hover_base = QColor(self.palette().highlight().color())
        hover_base.setAlpha(55)
        self._hover_color = hover_base
        self._hover_fill = _blend(
            QColor(self.palette().color(QPalette.ColorRole.Window)),
            QColor(self.palette().highlight().color()),
            0.25,
        )
        self._sel_color = QColor(self.palette().highlight().color())
        self._sel_text = QColor(self.palette().highlightedText().color())
        self._hover_row = -1
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_clicked)

    # ------------------------------------------------------------------
    #  Rendering
    # ------------------------------------------------------------------

    def refresh_items(self, items: list[SessionItem]) -> None:
        self._hover_row = -1
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
        # Progress is display-only; let mouse events pass through so hover and
        # row selection work even when the cursor is over the bar.
        progress_host = QWidget()
        progress_host.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
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

        self._apply_row_style(item.id, row, item.state)

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

        self._apply_row_style(item.id, row, item.state)

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
            status_item.setText("Downloading\u2026")

    def remove_item(self, item_id: str) -> None:
        row = self._row_for_id.pop(item_id, None)
        self._state_for_id.pop(item_id, None)
        self._dest_for_id.pop(item_id, None)
        self._url_for_id.pop(item_id, None)
        self._progress_for_id.pop(item_id, None)
        if row is not None:
            self.removeRow(row)
            self._reindex()
        self._hover_row = -1

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

    def _apply_row_style(self, item_id: str, row: int, state: str) -> None:
        """Colour the row's key text (name, size, status) + progress bar by state."""
        self._color_row(row, state)
        state_color = _COLORS.get(state, _COLORS[STATE_QUEUED])

        for col in (_COL_ITEM, _COL_SIZE, _COL_STATUS):
            cell = self.item(row, col)
            if cell is not None:
                cell.setForeground(
                    _DASH_COLOR if cell.text() == _DASH else state_color
                )

        # Neutral grey for the live-stat dashes.
        for col in (_COL_SPEED, _COL_ETA):
            cell = self.item(row, col)
            if cell is not None and cell.text() == _DASH:
                cell.setForeground(_DASH_COLOR)

        widget = self._progress_for_id.get(item_id)
        if isinstance(widget, QProgressBar):
            widget.setStyleSheet(self._bar_stylesheet(state, None))

    def _bar_stylesheet(self, state: str, band: QColor | None, selected: bool = False) -> str:
        """Stylesheet for a progress bar. ``band`` tints the whole track to the
        row's hover/selection colour (progress cell is a real widget, so the band
        must be painted on the bar itself rather than composited underneath)."""
        fill = _BAR_FILL.get(state)
        if band is None:
            background = "transparent"
            text_color = ""
        elif selected:
            background = _rgba(band)
            text_color = "#ffffff"
        else:
            background = _rgba(band)
            text_color = "#ffffff" if band.lightness() < 128 else "#000000"
        css = (
            f"QProgressBar {{ background: {background};"
            f"{f' color: {text_color};' if text_color else ''}"
            " text-align: center;"
            " border: 1px solid rgba(120,120,120,110); border-radius: 3px; }"
        )
        if fill:
            css += f"QProgressBar::chunk {{ background-color: {fill}; border-radius: 2px; }}"
        return css

    @staticmethod
    def _status_text(item: SessionItem) -> str:
        if item.state == STATE_COMPLETED:
            return "Done"
        if item.state == STATE_ACTIVE:
            return "Downloading\u2026"
        if item.state == STATE_FAILED:
            if item.error == "Not found":
                return "Failed: Not found"
            short = (item.error or "Failed").replace("\n", " ")
            return f"Failed \u2014 {short[:60]}"
        if item.state == STATE_CANCELLED:
            return "Cancelled"
        if item.attempts > 0:
            return "Queued (retry)"
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

    # ------------------------------------------------------------------
    #  Row hover (qBittorrent-style whole-row highlight)
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.viewport():
            event_type = event.type()
            if event_type == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                pos = event.position().toPoint()
                self._set_hover_row(self.rowAt(pos.y()))
            elif event_type == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
                pos = event.position().toPoint()
                if self.rowAt(pos.y()) < 0:
                    self.clearSelection()
            elif event_type == QEvent.Type.Leave:
                self._set_hover_row(-1)
        return super().eventFilter(obj, event)

    def _set_hover_row(self, row: int) -> None:
        if row == self._hover_row:
            return
        old = self._hover_row
        self._hover_row = row
        self.viewport().update()
        self._sync_hosts({old, row})

    def _item_id_for_row(self, row: int) -> str | None:
        for item_id, r in self._row_for_id.items():
            if r == row:
                return item_id
        return None

    def _sync_hosts(self, rows) -> None:
        """Tint each Progress bar's track with its row's hover/selection band."""
        for row in rows:
            if row < 0 or row >= self.rowCount():
                continue
            item_id = self._item_id_for_row(row)
            if item_id is None:
                continue
            if self.selectionModel().isRowSelected(row, self.model().index(0, 0).parent()):
                band = self._sel_color
                selected = True
            elif row == self._hover_row:
                band = self._hover_fill
                selected = False
            else:
                band = None
                selected = False
            bar = self._progress_for_id.get(item_id)
            if isinstance(bar, QProgressBar):
                bar.setStyleSheet(
                    self._bar_stylesheet(
                        self._state_for_id.get(item_id, STATE_QUEUED), band, selected
                    )
                )

    def _on_selection_changed(self, _selected, _deselected) -> None:
        rows: set[int] = set()
        for index in _selected.indexes():
            rows.add(index.row())
        for index in _deselected.indexes():
            rows.add(index.row())
        self._sync_hosts(rows)

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
