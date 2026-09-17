"""Registro de eventos a archivo.

Un fallo en la PC del gimnasio se diagnostica por telefono, asi que las trazas
tienen que quedar guardadas en disco y no solo en una consola que nadie ve.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from gym.config import logs_dir

FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    _close_handlers(root)

    file_handler = RotatingFileHandler(
        logs_dir() / "gym.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(console)

    # SQLAlchemy es muy conversador en INFO y ahogaria el resto del registro.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)


def reset_logging() -> None:
    """Cierra el archivo de log. En Windows pytest no puede borrar tmp si sigue abierto."""
    _close_handlers(logging.getLogger())


def _close_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def install_exception_hook() -> None:
    """Deja constancia de cualquier error no atendido antes de que la app muera."""

    def handler(exc_type, exc_value, traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, traceback)
            return
        logging.getLogger("gym").critical(
            "Error no controlado", exc_info=(exc_type, exc_value, traceback)
        )

    sys.excepthook = handler
