"""Vector icons drawn with QPainter, so the UI needs no external assets."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

_GRID = 20.0
_SCALE = 2


def _new_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size * _SCALE, size * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap


def _new_painter(pixmap: QPixmap, size: int) -> QPainter:
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size * _SCALE / _GRID, size * _SCALE / _GRID)
    return painter


def _stroke(width: float = 1.7) -> QPen:
    pen = QPen()
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw(painter: QPainter, name: str, color: QColor) -> None:
    pen = _stroke()
    pen.setColor(color)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "plus":
        painter.drawLine(QPointF(10, 4.8), QPointF(10, 15.2))
        painter.drawLine(QPointF(4.8, 10), QPointF(15.2, 10))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(2.6, 7.2)
        path.lineTo(8.0, 7.2)
        path.lineTo(9.4, 9.0)
        path.lineTo(17.4, 9.0)
        path.lineTo(17.4, 16.2)
        path.lineTo(2.6, 16.2)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(2.6, 9.0), QPointF(17.4, 9.0))
    elif name == "image":
        painter.drawRoundedRect(QRectF(2.8, 3.4, 14.4, 13.2), 2.2, 2.2)
        painter.drawEllipse(QRectF(6.2, 6.4, 3.0, 3.0))
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(4.0, 14.8),
                    QPointF(8.2, 10.2),
                    QPointF(10.8, 12.6),
                    QPointF(12.8, 10.4),
                    QPointF(16.2, 14.8),
                ]
            )
        )
    elif name == "trash":
        painter.drawLine(QPointF(3.8, 5.8), QPointF(16.2, 5.8))
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(8.0, 5.8),
                    QPointF(8.0, 3.8),
                    QPointF(12.0, 3.8),
                    QPointF(12.0, 5.8),
                ]
            )
        )
        painter.drawRoundedRect(QRectF(5.4, 6.2, 9.2, 10.2), 1.8, 1.8)
        painter.drawLine(QPointF(8.4, 8.6), QPointF(8.4, 14.2))
        painter.drawLine(QPointF(11.6, 8.6), QPointF(11.6, 14.2))
    elif name == "clear":
        painter.drawEllipse(QRectF(3.4, 3.4, 13.2, 13.2))
        painter.drawLine(QPointF(6.4, 13.6), QPointF(13.6, 6.4))
    elif name == "cancel":
        painter.drawLine(QPointF(5.4, 5.4), QPointF(14.6, 14.6))
        painter.drawLine(QPointF(14.6, 5.4), QPointF(5.4, 14.6))
    elif name == "play":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(7.0, 4.6), QPointF(15.8, 10.0), QPointF(7.0, 15.4)]))
    elif name == "open":
        painter.drawRoundedRect(QRectF(2.8, 3.6, 13.2, 12.8), 2.2, 2.2)
        painter.drawLine(QPointF(10.6, 9.4), QPointF(16.8, 3.2))
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(11.8, 3.2),
                    QPointF(16.8, 3.2),
                    QPointF(16.8, 8.2),
                ]
            )
        )
    elif name == "sun":
        painter.drawEllipse(QRectF(7.2, 7.2, 5.6, 5.6))
        for index in range(8):
            angle = math.radians(index * 45)
            inner = 6.6
            outer = 8.6
            painter.drawLine(
                QPointF(10 + inner * math.cos(angle), 10 + inner * math.sin(angle)),
                QPointF(10 + outer * math.cos(angle), 10 + outer * math.sin(angle)),
            )
    elif name == "moon":
        body = QPainterPath()
        body.addEllipse(QRectF(3.4, 2.6, 14.0, 14.0))
        cut = QPainterPath()
        cut.addEllipse(QRectF(8.0, 0.6, 13.0, 13.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(body.subtracted(cut))
    elif name == "monitor":
        painter.drawRoundedRect(QRectF(2.8, 4.2, 14.4, 9.6), 2.0, 2.0)
        painter.drawLine(QPointF(10, 13.8), QPointF(10, 16.2))
        painter.drawLine(QPointF(7.2, 16.4), QPointF(12.8, 16.4))
    elif name == "settings":
        # Engranaje: corona de 8 dientes con hueco central (no un sol).
        gear = QPainterPath()
        teeth = 8
        step = math.tau / teeth
        outer, root = 7.9, 5.6
        for index in range(teeth):
            center_angle = index * step - math.pi / 2
            for offset, radius in ((-0.34, root), (-0.20, outer), (0.20, outer), (0.34, root)):
                angle = center_angle + offset * step
                point = QPointF(
                    10 + radius * math.cos(angle),
                    10 + radius * math.sin(angle),
                )
                if index == 0 and offset == -0.34:
                    gear.moveTo(point)
                else:
                    gear.lineTo(point)
        gear.closeSubpath()
        hole = QPainterPath()
        hole.addEllipse(QRectF(7.5, 7.5, 5.0, 5.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(gear.subtracted(hole))
    elif name == "warning":
        path = QPainterPath()
        path.moveTo(10, 3.2)
        path.lineTo(17.4, 16.2)
        path.lineTo(2.6, 16.2)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(10, 8.0), QPointF(10, 12.0))
        painter.drawPoint(QPointF(10, 14.0))
    elif name == "refresh":
        path = QPainterPath()
        path.arcMoveTo(QRectF(4.2, 4.2, 11.6, 11.6), 40)
        path.arcTo(QRectF(4.2, 4.2, 11.6, 11.6), 40, 285)
        painter.drawPath(path)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(13.6, 3.8),
                    QPointF(16.2, 6.6),
                    QPointF(12.8, 7.6),
                ]
            )
        )


def icon(name: str, color: str | QColor, size: int = 18) -> QIcon:
    """Return a crisp QIcon for a named glyph."""
    return QIcon(pixmap(name, color, size))


def pixmap(name: str, color: str | QColor, size: int = 18) -> QPixmap:
    """Return a device-pixel-ratio aware pixmap for a named glyph."""
    pixmap_ = _new_pixmap(size)
    painter = _new_painter(pixmap_, size)
    _draw(painter, name, QColor(color))
    painter.end()
    pixmap_.setDevicePixelRatio(_SCALE)
    return pixmap_


def swatch(color: str | QColor, size: int = 16) -> QIcon:
    """Filled circle used as the preview of an accent color in menus."""
    pixmap_ = _new_pixmap(size)
    painter = _new_painter(pixmap_, size)
    painter.setPen(QPen(QColor(0, 0, 0, 45), 0.9))
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(2.8, 2.8, 14.4, 14.4))
    painter.end()
    pixmap_.setDevicePixelRatio(_SCALE)
    return QIcon(pixmap_)


def app_logo(size: int = 44) -> QPixmap:
    """Rounded gradient tile with the app glyph, used as window icon."""
    pixmap_ = _new_pixmap(size)
    painter = _new_painter(pixmap_, size)
    gradient = QLinearGradient(0, 0, _GRID, _GRID)
    gradient.setColorAt(0.0, QColor("#2B88D8"))
    gradient.setColorAt(1.0, QColor("#005FB8"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(0, 0, _GRID, _GRID), 4.6, 4.6)

    painter.translate(4.4, 4.4)
    painter.scale(0.56, 0.56)
    white = QColor("#FFFFFF")
    pen = _stroke(2.1)
    pen.setColor(white)
    painter.setPen(pen)
    painter.drawRoundedRect(QRectF(2.8, 3.4, 14.4, 13.2), 2.4, 2.4)
    painter.drawEllipse(QRectF(6.2, 6.4, 3.0, 3.0))
    painter.drawPolyline(
        QPolygonF(
            [
                QPointF(4.0, 14.8),
                QPointF(8.2, 10.2),
                QPointF(10.8, 12.6),
                QPointF(12.8, 10.4),
                QPointF(16.2, 14.8),
            ]
        )
    )
    painter.end()
    pixmap_.setDevicePixelRatio(_SCALE)
    return pixmap_
