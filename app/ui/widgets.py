"""Small reusable widgets: Windows 11 style toggle and the empty-aware table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QComboBox, QTableView

from app.i18n import tr
from app.ui.icons import pixmap


class ToggleSwitch(QAbstractButton):
    """Animated pill switch used instead of native checkboxes."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(tr("toggle.accessible"))
        self._accent = QColor("#0067C0")
        self._track = QColor("#C8C8C8")
        self._knob_position = 0.0
        self._animation = QPropertyAnimation(self, b"knob_position", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob_position(self) -> float:
        return self._knob_position

    def _set_knob_position(self, value: float) -> None:
        self._knob_position = value
        self.update()

    knob_position = Property(float, _get_knob_position, _set_knob_position)

    def set_colors(self, accent: str | QColor, track: str | QColor) -> None:
        self._accent = QColor(accent)
        self._track = QColor(track)
        self.update()

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            painter.setOpacity(0.45)

        track = QRectF(1.0, 2.0, 40.0, 20.0)
        background = QColor(self._accent) if self.isChecked() else QColor(self._track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(track, 10.0, 10.0)

        knob_x = 3.0 + self._knob_position * 20.0
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, 4.0, 16.0, 16.0))

        if self.hasFocus():
            pen = QPen(self._accent)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.6, 1.6, 40.8, 20.8), 10.4, 10.4)
        painter.end()


class SelectComboBox(QComboBox):
    """Select field with a hand-drawn chevron and a roomier hit area.

    The native arrow is hidden from QSS so the chevron can follow the palette
    (muted normally, accent on hover/focus) in both themes.
    """

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Select")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt signature
        super().paintEvent(event)  # type: ignore[arg-type]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self.isEnabled():
            color = self.palette().color(QPalette.ColorRole.Mid)
        elif self.hasFocus() or self.underMouse():
            color = self.palette().color(QPalette.ColorRole.Highlight)
        else:
            color = self.palette().color(QPalette.ColorRole.PlaceholderText)

        pen = QPen(color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = self.width() - 16.0
        center_y = self.height() / 2.0
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(center_x - 4.0, center_y - 2.0),
                    QPointF(center_x, center_y + 2.4),
                    QPointF(center_x + 4.0, center_y - 2.0),
                ]
            )
        )
        painter.end()


class FileTable(QTableView):
    """QTableView with reordering, multi-selection and an empty state.

    Files dropped from Explorer are forwarded as :attr:`pathsDropped`; rows
    dragged inside the view are reordered through the model. When the queue is
    empty the view paints the old drop-zone look and a click opens the file
    picker (:attr:`browseRequested`).
    """

    pathsDropped = Signal(list)  # list[Path]
    rowsReordered = Signal(list)  # list[int] nuevas filas
    browseRequested = Signal()

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # -------------------------------------------------------------- drag/drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        if event.mimeData().hasUrls():
            self._set_drag_active(True)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if event.source() is self or event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        if event.source() is self:
            self._drop_rows(event)
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.pathsDropped.emit(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        model = self.model()
        empty = model is None or model.rowCount() == 0
        if (
            event.button() is Qt.MouseButton.LeftButton
            and empty
            and self.viewport().rect().contains(event.position().toPoint())
        ):
            self.browseRequested.emit()
        super().mouseReleaseEvent(event)

    def _set_drag_active(self, active: bool) -> None:
        if bool(self.property("dragActive")) == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.viewport().update()

    def _drop_rows(self, event: QDropEvent) -> None:
        model = self.model()
        if model is None or not hasattr(model, "move_rows"):
            event.ignore()
            return
        selection = self.selectionModel()
        rows = sorted({index.row() for index in selection.selectedRows()}) if selection else []
        if not rows:
            event.ignore()
            return

        position = event.position().toPoint()
        index = self.indexAt(position)
        target = index.row() if index.isValid() else model.rowCount()
        block = set(rows)
        if target in block or target in {row + 1 for row in block}:
            event.acceptProposedAction()
            return

        new_rows = model.move_rows(rows, target)  # type: ignore[attr-defined]
        if selection is not None and new_rows:
            selection.clearSelection()
            flags = QAbstractItemView.SelectionFlag.Select | QAbstractItemView.SelectionFlag.Rows
            for row in new_rows:
                selection.select(model.index(row, 0), flags)
        self.rowsReordered.emit(list(new_rows))
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt signature
        super().paintEvent(event)  # type: ignore[arg-type]
        model = self.model()
        if model is None or model.rowCount() == 0:
            self._paint_empty()

    def _paint_empty(self) -> None:
        viewport = self.viewport()
        painter = QPainter(viewport)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self.palette().color(self.foregroundRole())
        muted = self.palette().color(QPalette.ColorRole.PlaceholderText)
        accent = self.palette().color(QPalette.ColorRole.Highlight)
        active = bool(self.property("dragActive"))

        # La cola vacía imita la antigua zona de arrastre: tarjeta punteada.
        border = accent if active else self.palette().color(QPalette.ColorRole.Mid)
        fill = self.palette().color(QPalette.ColorRole.AlternateBase)
        card = QRectF(viewport.rect()).adjusted(12, 12, -12, -12)
        border_pen = QPen(border)
        border_pen.setWidthF(1.5)
        border_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(border_pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(card, 12, 12)

        side = 44
        center_x = viewport.width() / 2
        center_y = viewport.height() / 2
        glyph = pixmap("image", accent if active else muted, side)
        painter.drawPixmap(
            QRectF(center_x - side / 2, center_y - 66, side, side),
            glyph,
            QRectF(0, 0, side, side),
        )

        title_font = self.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 1.5)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(color)
        painter.drawText(
            QRectF(0, center_y - 10, viewport.width(), 26),
            Qt.AlignmentFlag.AlignCenter,
            tr("empty.title"),
        )

        hint_font = self.font()
        hint_font.setPointSizeF(max(8.0, hint_font.pointSizeF() - 0.5))
        painter.setFont(hint_font)
        painter.setPen(muted)
        painter.drawText(
            QRectF(0, center_y + 18, viewport.width(), 26),
            Qt.AlignmentFlag.AlignCenter,
            tr("empty.hint"),
        )
        painter.end()
