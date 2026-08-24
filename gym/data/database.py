"""Motor de base de datos y manejo de sesiones."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from gym.config import database_path

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _configure_connection(dbapi_connection, _connection_record) -> None:
    """Ajustes por conexion que SQLite no conserva entre sesiones."""
    cursor = dbapi_connection.cursor()
    # SQLite ignora las llaves foraneas salvo que se activen explicitamente.
    cursor.execute("PRAGMA foreign_keys=ON")
    # WAL permite leer mientras se escribe y sobrevive mejor a un corte de luz.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Espera en vez de fallar si otra conexion tiene el archivo tomado.
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_db_engine(path: Path | str | None = None, echo: bool = False) -> Engine:
    target = "sqlite://" if path == ":memory:" else f"sqlite:///{path or database_path()}"
    engine = create_engine(target, echo=echo, future=True)
    event.listen(engine, "connect", _configure_connection)
    return engine


def init_engine(path: Path | str | None = None, echo: bool = False) -> Engine:
    """Inicializa el motor global. Se llama una vez al arrancar la aplicacion."""
    global _engine, _session_factory
    _engine = create_db_engine(path, echo=echo)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return init_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sesion transaccional: confirma al salir bien, revierte ante cualquier error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Cierra el pool para liberar el archivo antes de restaurar un respaldo."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
