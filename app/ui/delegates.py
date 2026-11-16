"""Item delegates: rounded thumbnails and colored status pills."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from app.models import JobStatus
from app.ui.file_model import ITEM_ROLE, FileItem, status_label
from app.ui.icons import pixmap

_STATUS_COLORS = {
    JobStatus.PENDING: ("#6E6E6E", "#A6A6A6"),
    JobStatus.RUNNING: ("#0067C0", "#4CC2FF"),
    JobStatus.DONE: ("#0F7B0F", "#6CCB5F"),
    JobStatus.SKIPPED: ("#9D5D00", "#FCE100"),
    JobStatus.ERROR: ("#C42B1C", "#FF99A4"),
}


class ThumbnailDelegate(QStyledItemDelegate):
    """Draws the preview cell as a rounded thumbnail or a placeholder."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._placeholder: QPixmap | None = None
        self._placeholder_color = ""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        item = index.data(ITEM_ROLE)
        if not isinstance(item, FileItem):
            return

        side = min(option.rect.height() - 16, option.rect.width() - 20, 44)
        box = QRectF(
            option.rect.x() + 12,
            option.rect.y() + (option.rect.height() - side) / 2,
            side,
            side,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(option.palette.color(QPalette.ColorRole.AlternateBase))
        painter.drawRoundedRect(box, 7.0, 7.0)

        if item.thumbnail is not None and not item.thumbnail.isNull():
            path = QPainterPath()
            path.addRoundedRect(box, 7.0, 7.0)
            painter.setClipPath(path)
            image = QPixmap.fromImage(item.thumbnail)
            scaled = image.scaled(
                int(side),
                int(side),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = box.x() + (side - scaled.width()) / 2
            y = box.y() + (side - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            muted = option.palette.color(QPalette.ColorRole.PlaceholderText)
            if self._placeholder is None or self._placeholder_color != muted.name():
                self._placeholder = pixmap("image", muted, 18)
                self._placeholder_color = muted.name()
            icon_side = 18
            painter.drawPixmap(
                QRectF(
                    box.x() + (side - icon_side) / 2,
                    box.y() + (side - icon_side) / 2,
                    icon_side,
                    icon_side,
                ),
                self._placeholder,
                QRectF(0, 0, icon_side, icon_side),
            )
        painter.restore()


class StatusDelegate(QStyledItemDelegate):
    """Renders the status as a pill instead of plain text."""

    def __init__(self, parent: object | None = None, dark: bool = False) -> None:
        super().__init__(parent)
        self._dark = dark

    def set_dark(self, dark: bool) -> None:
        self._dark = dark

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        item = index.data(ITEM_ROLE)
        if not isinstance(item, FileItem):
            return

        label = status_label(item.status)
        light_color, dark_color = _STATUS_COLORS.get(item.status, _STATUS_COLORS[JobStatus.PENDING])
        color = QColor(dark_color if self._dark else light_color)

        font = QFont(option.font)
        font.setPointSizeF(max(8.0, font.pointSizeF() - 0.8))
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(font)
        width = min(option.rect.width() - 12, metrics.horizontalAdvance(label) + 22)
        height = 22
        badge = QRectF(
            option.rect.x() + (option.rect.width() - width) / 2,
            option.rect.y() + (option.rect.height() - height) / 2,
            width,
            height,
        )

        background = QColor(color)
        background.setAlpha(48 if self._dark else 30)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(badge, height / 2, height / 2)

        if item.status is JobStatus.ERROR:
            pen = QPen(color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(badge, height / 2, height / 2)

        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()
