"""Respaldos de la base de datos.

Se usa `VACUUM INTO` en vez de copiar el archivo: con el modo WAL activo, una
copia simple puede capturar la base sin los cambios que aun viven en el diario
y producir un respaldo corrupto. `VACUUM INTO` escribe una base consistente y ya
compactada, aunque haya escrituras en curso.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from gym.config import Settings, backups_dir, database_path
from gym.data.database import dispose_engine, get_engine, init_engine

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "gym-"
BACKUP_SUFFIX = ".sqlite"


@dataclass
class BackupFile:
    path: Path
    created_at: datetime
    size_bytes: int

    @property
    def size_label(self) -> str:
        mb = self.size_bytes / (1024 * 1024)
        if mb >= 1:
            return f"{mb:.1f} MB"
        return f"{self.size_bytes / 1024:.0f} KB"


def create_backup(moment: datetime | None = None) -> Path:
    moment = moment or datetime.now()
    target = backups_dir() / f"{BACKUP_PREFIX}{moment:%Y%m%d-%H%M%S}{BACKUP_SUFFIX}"

    # VACUUM INTO falla si el destino ya existe.
    if target.exists():
        target = target.with_name(f"{target.stem}-{moment.microsecond}{BACKUP_SUFFIX}")

    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("VACUUM INTO :path"), {"path": str(target)})

    logger.info("Respaldo creado en %s", target)
    return target


def list_backups() -> list[BackupFile]:
    """Respaldos existentes, del mas reciente al mas antiguo."""
    files = []
    for path in backups_dir().glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            BackupFile(
                path=path,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=stat.st_size,
            )
        )
    return sorted(files, key=lambda item: item.created_at, reverse=True)


def prune_backups(keep: int) -> int:
    """Conserva los `keep` mas recientes y borra el resto."""
    if keep <= 0:
        return 0

    removed = 0
    for backup in list_backups()[keep:]:
        try:
            backup.path.unlink()
            removed += 1
        except OSError:
            logger.warning("No se pudo borrar el respaldo %s", backup.path)
    if removed:
        logger.info("Se eliminaron %s respaldos antiguos", removed)
    return removed


def run_backup(settings: Settings) -> Path:
    path = create_backup()
    prune_backups(settings.backups_to_keep)
    return path


def run_exit_backup(settings: Settings) -> Path | None:
    if not settings.backup_on_exit:
        return None
    return run_backup(settings)


def restore_backup(source: Path) -> None:
    """Sustituye la base actual por un respaldo.

    Antes de sobrescribir se guarda una copia del estado presente: si el
    respaldo elegido resulta ser el equivocado, todavia hay camino de regreso.
    """
    if not source.exists():
        raise FileNotFoundError(f"No se encontró el respaldo {source.name}.")

    current = database_path()

    safety = None
    if current.exists():
        safety = create_backup()
        logger.info("Copia de seguridad previa a la restauracion: %s", safety)

    dispose_engine()

    # Los diarios del WAL pertenecen a la base anterior; dejarlos ahi corromperia
    # la restaurada.
    for extra in (
        current.with_name(current.name + "-wal"),
        current.with_name(current.name + "-shm"),
    ):
        extra.unlink(missing_ok=True)

    shutil.copy2(source, current)
    init_engine()
    logger.info("Base restaurada desde %s", source)
