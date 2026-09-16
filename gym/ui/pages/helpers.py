"""Ayudas visuales compartidas entre pantallas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPixmap

from gym.services.members import photo_path
from gym.ui.theme import NEUTRAL_BG, TEXT


def avatar_pixmap(photo_name: str | None, initials: str, size: int = 48) -> QPixmap:
    """Foto recortada en circulo o, si no hay, un circulo gris con las iniciales."""
    return _photo_pixmap(photo_name, initials, size, circle=True)


def slot_pixmap(photo_name: str | None, initials: str, size: int = 340) -> QPixmap:
    """Foto que llena el recuadro redondeado del kiosco."""
    return _photo_pixmap(photo_name, initials, size, circle=False)


def _photo_pixmap(photo_name: str | None, initials: str, size: int, *, circle: bool) -> QPixmap:
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    path = QPainterPath()
    if circle:
        path.addEllipse(0, 0, size, size)
    else:
        path.addRoundedRect(0, 0, size, size, 12, 12)
    painter.setClipPath(path)

    source = photo_path(photo_name)
    photo = QPixmap(str(source)) if source else QPixmap()

    if not photo.isNull():
        scaled = photo.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    else:
        painter.fillPath(path, QBrush(QColor(NEUTRAL_BG)))
        painter.setPen(QColor(TEXT))
        font = QFont()
        font.setPointSize(max(9, size // 3))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, initials or "?")

    painter.end()
    return canvas
