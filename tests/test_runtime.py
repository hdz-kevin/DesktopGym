"""Pruebas de instancia unica y registro de eventos."""

from __future__ import annotations

import logging
import os

from gym.data.schema import prepare_database
from gym.logging_setup import configure_logging, reset_logging
from gym.single_instance import InstanceLock


class TestInstanciaUnica:
    def test_la_primera_toma_el_candado(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        lock = InstanceLock()
        try:
            assert lock.acquire()
        finally:
            lock.release()

    def test_la_segunda_no_puede_abrir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        primera = InstanceLock()
        segunda = InstanceLock()
        try:
            assert primera.acquire()
            assert not segunda.acquire()
        finally:
            primera.release()
            segunda.release()

    def test_al_soltarlo_otra_puede_entrar(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        primera = InstanceLock()
        segunda = InstanceLock()
        try:
            primera.acquire()
            primera.release()
            assert segunda.acquire()
        finally:
            segunda.release()

    def test_guarda_el_pid(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        lock = InstanceLock()
        try:
            lock.acquire()
            # En Windows no se puede reabrir gym.lock mientras esta bloqueado.
            assert lock.pid() == str(os.getpid())
        finally:
            lock.release()

    def test_si_el_archivo_existe_y_no_se_abre_ya_hay_otra_ventana(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        lock = InstanceLock()
        lock.path.write_text("1", encoding="utf-8")

        def boom(*_args, **_kwargs):
            raise PermissionError("denied")

        monkeypatch.setattr("builtins.open", boom)
        assert not lock.acquire()


class TestRegistro:
    def test_escribe_en_el_archivo(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        configure_logging()
        try:
            logging.getLogger("gym.prueba").info("hola")
            contenido = (tmp_path / "logs" / "gym.log").read_text(encoding="utf-8")
            assert "hola" in contenido
        finally:
            reset_logging()

    def test_migrar_no_deja_la_app_sin_archivo_de_registro(self, tmp_path, monkeypatch):
        """Alembic reconfigura el logging; la app no debe perder su archivo."""
        monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
        configure_logging()
        try:
            from gym.data import database

            database.dispose_engine()
            database.init_engine()
            prepare_database()

            logging.getLogger("gym.prueba").info("despues de migrar")
            database.dispose_engine()

            contenido = (tmp_path / "logs" / "gym.log").read_text(encoding="utf-8")
            assert "despues de migrar" in contenido
        finally:
            reset_logging()
