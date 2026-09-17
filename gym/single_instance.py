"""Bloqueo de instancia unica.

Dos ventanas escribiendo sobre el mismo SQLite terminarian mostrando datos
distintos del mismo socio y compitiendo por el archivo.
"""

from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path

from gym.config import data_dir


class InstanceLock:
    def __init__(self, name: str = "gym.lock") -> None:
        self.path: Path = data_dir() / name
        self._handle = None

    def acquire(self) -> bool:
        try:
            # El archivo se queda abierto a proposito: el candado del sistema
            # operativo vive mientras exista el descriptor, asi que cerrarlo con
            # un context manager liberaria el bloqueo de inmediato.
            self._handle = open(self.path, "a+", encoding="utf-8")  # noqa: SIM115
        except OSError:
            # En Windows, abrir un archivo ya bloqueado tambien lanza
            # PermissionError. Si el candado existe, otra instancia esta
            # dentro. Si no pudimos crearlo (carpeta de solo lectura), es
            # preferible dejar entrar.
            return not self.path.exists()

        try:
            # msvcrt.locking bloquea desde la posicion actual, no el archivo
            # entero: hay que ir al byte 0 o dos instancias podrian tomarlo.
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            return False

        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()
        return True

    def pid(self) -> str:
        """Lee el PID del descriptor abierto: en Windows no se puede reabrir."""
        if self._handle is None:
            return ""
        self._handle.seek(0)
        return self._handle.read().strip()

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None
            # En Windows el desbloqueo a veces tarda un instante; el
            # siguiente arranque reutiliza el archivo.
            with suppress(OSError):
                self.path.unlink(missing_ok=True)
