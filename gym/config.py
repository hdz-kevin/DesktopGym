"""Configuracion y rutas de datos de la aplicacion.

Los datos nunca viven junto al ejecutable: en Windows `Program Files` es de solo
lectura y la aplicacion fallaria al escribir la base de datos.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Identidad del programa: instalador, .exe y carpeta de datos. El nombre que
# ve el recepcionista en pantalla es Settings.gym_name, distinto en cada PC.
APP_NAME = "DevGym"


def data_dir() -> Path:
    """Carpeta de datos del usuario, creada si no existe."""
    override = os.environ.get("GYM_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME

    base.mkdir(parents=True, exist_ok=True)
    return base


def database_path() -> Path:
    return data_dir() / "gym.sqlite"


def photos_dir() -> Path:
    path = data_dir() / "photos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    """Ruta a un recurso empaquetado, compatible con PyInstaller."""
    bundle = getattr(sys, "_MEIPASS", None)
    base = Path(bundle) if bundle else Path(__file__).resolve().parent
    return base / relative


@dataclass
class Settings:
    """Ajustes editables por el usuario. Reemplaza a config/gym.php."""

    gym_name: str = "Gimnasio"
    gym_address: str = "Av. Miguel Hidalgo #123, Teziutlán"
    visit_price_cents: int = 4000
    backup_on_exit: bool = True
    backups_to_keep: int = 30

    @classmethod
    def load(cls) -> Settings:
        path = data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f: raw[f] for f in cls.__dataclass_fields__ if f in raw}
        return cls(**known)

    def save(self) -> None:
        path = data_dir() / "settings.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
