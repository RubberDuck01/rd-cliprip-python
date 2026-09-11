from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPalette, QPen
from PyQt6.QtWidgets import QApplication, QStyle, QStyledItemDelegate


def _blend(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


def _rgba(color: QColor) -> str:
    return f"rgba({color.red()},{color.green()},{color.blue()},{color.alpha()})"


class BandDelegate(QStyledItemDelegate):
    """Paint selection / hover as one plain band per row (qBittorrent-like).

    The table must have been prepared by ``install_row_band`` (it stores the
    colours and the hovered row on the table itself).
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
            alignment = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        rect = option.rect.adjusted(4, 0, -4, 0)
        elided = painter.fontMetrics().elidedText(
            str(text), Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.drawText(rect, alignment, elided)


def install_row_band(table) -> None:
    """Give a QTableWidget the shared whole-row hover/selection behaviour."""
    highlight = QColor(table.palette().highlight().color())
    window = QColor(table.palette().color(QPalette.ColorRole.Window))
    table._sel_color = QColor(highlight)
    table._hover_fill = _blend(window, highlight, 0.25)
    hover_tint = QColor(highlight)
    hover_tint.setAlpha(55)
    table._hover_color = hover_tint
    table._sel_text = QColor(table.palette().highlightedText().color())
    table._hover_row = -1
    table.setItemDelegate(BandDelegate(table))
    table.viewport().setMouseTracking(True)


def set_hover_row(table, row: int) -> None:
    if row == table._hover_row:
        return
    table._hover_row = row
    table.viewport().update()


def band_event_filter(table, event) -> bool:
    """Handle hover + click-empty-to-deselect for a row-band table.

    Returns True when the event was consumed.
    """
    event_type = event.type()
    if event_type == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
        pos = event.position().toPoint()
        set_hover_row(table, table.rowAt(pos.y()))
    elif event_type == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
        pos = event.position().toPoint()
        if table.rowAt(pos.y()) < 0:
            table.clearSelection()
    elif event_type == QEvent.Type.Leave:
        set_hover_row(table, -1)
    return False
