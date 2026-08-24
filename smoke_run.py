"""Arranque real de la aplicacion que se cierra solo, para verificacion manual.

Se ejecuta con: uv run python smoke_run.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import gym.__main__ as entry

HOLD_MS = 2500


def main() -> int:
    original_build = entry.build_window

    def build_and_schedule_quit(settings):
        window = original_build(settings)
        # El cierre se programa aqui y no antes: hasta que existe QApplication,
        # un QTimer no tiene bucle de eventos donde dispararse.
        QTimer.singleShot(HOLD_MS, QApplication.instance().quit)
        return window

    entry.build_window = build_and_schedule_quit
    return entry.main()


if __name__ == "__main__":
    code = main()
    print(f"La aplicación arrancó y cerró con código {code}")
    sys.exit(code)
