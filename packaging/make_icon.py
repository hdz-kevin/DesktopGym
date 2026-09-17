"""Genera el icono generico de DevGym.

Monograma DG sobre un recuadro redondeado: la mitad derecha va en azul de la
app para que se lea igual a 16 px y a 256 px. Se dibuja con Qt en vez de
guardar un binario a mano, asi el icono se ajusta en codigo.

Uso: uv run python packaging/make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QApplication

OUTPUT = Path(__file__).resolve().parent / "gym.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BACKGROUND = QColor("#151b26")
ACCENT = QColor("#2563eb")
LIGHT = QColor("#ffffff")


def _font(size: int) -> QFont:
    font = QFont()
    font.setFamilies(["Arial Black", "Segoe UI", "Arial", "Helvetica Neue", "DejaVu Sans"])
    font.setWeight(QFont.Weight.Black)
    # A 16 px las dos letras necesitan casi todo el recuadro; a partir de 32
    # hay margen para que el corte diagonal se lea como parte del diseno.
    font.setPixelSize(max(8, round(size * (0.54 if size >= 32 else 0.58))))
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    rounded = QPainterPath()
    rounded.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    painter.setClipPath(rounded)
    painter.fillPath(rounded, QBrush(BACKGROUND))

    # Corte diagonal: da un bloque de color a la G y un borde vivo a 16 px.
    split = QPainterPath()
    split.moveTo(size * 0.46, 0)
    split.lineTo(size, 0)
    split.lineTo(size, size)
    split.lineTo(size * 0.34, size)
    split.closeSubpath()
    painter.fillPath(split, QBrush(ACCENT))

    if size >= 24:
        shine = QLinearGradient(0, 0, 0, size * 0.4)
        shine.setColorAt(0, QColor(255, 255, 255, 30))
        shine.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillPath(rounded, QBrush(shine))

    font = _font(size)
    metrics = QFontMetricsF(font)
    gap = size * (0.02 if size >= 32 else 0.0)
    d_width = metrics.horizontalAdvance("D")
    g_width = metrics.horizontalAdvance("G")
    total = d_width + gap + g_width
    left = (size - total) / 2
    baseline = (size + metrics.ascent() - metrics.descent()) / 2 + size * 0.02

    painter.setFont(font)
    painter.setPen(LIGHT)
    painter.drawText(QPointF(left, baseline), "D")
    painter.drawText(QPointF(left + d_width + gap, baseline), "G")

    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, images: list[QImage]) -> None:
    """ICO con un PNG por tamano. Qt a veces no trae el codec ICO."""
    payloads = [_png_bytes(image) for image in images]
    offset = 6 + 16 * len(images)
    chunks = [struct.pack("<HHH", 0, 1, len(images))]
    for image, payload in zip(images, payloads, strict=True):
        side = image.width()
        stored = 0 if side >= 256 else side
        chunks.append(struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    path.write_bytes(b"".join(chunks) + b"".join(payloads))


def main() -> int:
    app = QApplication(sys.argv)
    images = [draw(size) for size in SIZES]
    write_ico(OUTPUT, images)
    print(f"Icono generado: {OUTPUT}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
