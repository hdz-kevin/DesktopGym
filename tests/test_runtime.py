"""Pruebas de instancia unica y registro de eventos."""

from __future__ import annotations

import logging

from gym.data.schema import prepare_database
from gym.logging_setup import configure_logging
from gym.single_instance import InstanceLock


class TestInstanciaUnica:
    def test_la_primera_toma_el_candado(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        lock = InstanceLock()
        assert lock.acquire()
        lock.release()

    def test_la_segunda_no_puede_abrir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        primera = InstanceLock()
        segunda = InstanceLock()

        assert primera.acquire()
        assert not segunda.acquire()

        primera.release()

    def test_al_soltarlo_otra_puede_entrar(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        primera = InstanceLock()
        primera.acquire()
        primera.release()

        segunda = InstanceLock()
        assert segunda.acquire()
        segunda.release()

    def test_guarda_el_pid(self, tmp_path, monkeypatch):
        import os

        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        lock = InstanceLock()
        lock.acquire()

        assert lock.path.read_text().strip() == str(os.getpid())
        lock.release()


class TestRegistro:
    def test_escribe_en_el_archivo(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        configure_logging()
        logging.getLogger("gym.prueba").info("hola")

        contenido = (tmp_path / "logs" / "gym.log").read_text(encoding="utf-8")
        assert "hola" in contenido

    def test_migrar_no_deja_la_app_sin_archivo_de_registro(self, tmp_path, monkeypatch):
        """Alembic reconfigura el logging; la app no debe perder su archivo."""
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        configure_logging()

        from gym.data import database

        database.dispose_engine()
        database.init_engine()
        prepare_database()

        logging.getLogger("gym.prueba").info("despues de migrar")
        database.dispose_engine()

        contenido = (tmp_path / "logs" / "gym.log").read_text(encoding="utf-8")
        assert "despues de migrar" in contenido
