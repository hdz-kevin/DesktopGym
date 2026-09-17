# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller: un solo ejecutable sin consola.

Las migraciones se incluyen como datos porque la aplicacion las ejecuta al
arrancar; si no viajaran dentro del .exe, la base nunca se crearia.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gym.config import APP_NAME

ICON = ROOT / "packaging" / "gym.ico"

a = Analysis(
    [str(ROOT / "gym" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "migrations"), "migrations"),
        (str(ROOT / "alembic.ini"), "."),
    ],
    hiddenimports=[
        # Alembic carga las migraciones por ruta, no por import: PyInstaller no
        # puede descubrirlas analizando el codigo.
        "alembic.runtime.migration",
        "logging.config",
        "sqlalchemy.dialects.sqlite",
        # La captura de foto importa estos al abrir el dialogo; sin ellos el
        # .exe no encuentra plugins de camara.
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.exists() else None,
)
