"""Genera el icono de la aplicacion.

Se dibuja con Qt en vez de guardar un binario en el repositorio, asi el icono
se puede ajustar cambiando unas lineas de codigo.

Uso: uv run python packaging/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication

OUTPUT = Path(__file__).resolve().parent / "gym.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BACKGROUND = QColor("#151b26")
ACCENT = QColor("#2563eb")
LIGHT = QColor("#ffffff")


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rounded = QPainterPath()
    radius = size * 0.22
    rounded.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.fillPath(rounded, QBrush(BACKGROUND))

    unit = size / 32.0
    painter.setPen(Qt.PenStyle.NoPen)

    # Barra central de la mancuerna.
    painter.setBrush(QBrush(LIGHT))
    painter.drawRoundedRect(QRectF(10 * unit, 14.6 * unit, 12 * unit, 2.8 * unit), unit, unit)

    # Discos de cada extremo.
    painter.setBrush(QBrush(ACCENT))
    for x in (5.5 * unit, 22.5 * unit):
        painter.drawRoundedRect(QRectF(x, 10 * unit, 4 * unit, 12 * unit), unit * 1.2, unit * 1.2)

    painter.setBrush(QBrush(LIGHT))
    for x in (9.5 * unit, 19.5 * unit):
        painter.drawRoundedRect(QRectF(x, 12 * unit, 3 * unit, 8 * unit), unit * 0.9, unit * 0.9)

    painter.end()
    return image


def main() -> int:
    app = QApplication(sys.argv)

    images = [draw(size) for size in SIZES]
    largest = images[-1]

    if not largest.save(str(OUTPUT), "ICO"):
        # Algunas compilaciones de Qt no traen el codificador ICO; el PNG sirve
        # igual para Inno Setup y para probar en otras plataformas.
        fallback = OUTPUT.with_suffix(".png")
        largest.save(str(fallback), "PNG")
        print(f"Qt no pudo escribir ICO; se generó {fallback}")
        return 1

    print(f"Icono generado: {OUTPUT}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
