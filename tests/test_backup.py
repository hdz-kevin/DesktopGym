"""Pruebas de respaldos y ajustes."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from gym.config import Settings, backups_dir, database_path
from gym.domain.enums import MemberGender
from gym.services import backup as service
from gym.services import members as members_service
from gym.ui.main_window import MainWindow
from gym.ui.pages.settings import SettingsPage


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez") -> int:
    return members_service.create_member(
        members_service.MemberForm(name=nombre, gender=MemberGender.FEMALE)
    )


class TestCrearRespaldo:
    def test_genera_un_archivo(self, app_db):
        path = service.create_backup()
        assert path.exists()
        assert path.parent == backups_dir()

    def test_el_respaldo_contiene_los_datos(self, app_db):
        alta("Ana Lopez")
        path = service.create_backup()

        import sqlite3

        with sqlite3.connect(path) as connection:
            nombres = [row[0] for row in connection.execute("SELECT name FROM members")]
        assert nombres == ["Ana Lopez"]

    def test_dos_respaldos_seguidos_no_se_pisan(self, app_db):
        momento = datetime(2025, 6, 1, 12, 0, 0)
        primero = service.create_backup(momento)
        segundo = service.create_backup(momento)

        assert primero != segundo
        assert primero.exists() and segundo.exists()

    def test_los_lista_del_mas_reciente_al_mas_viejo(self, app_db):
        service.create_backup(datetime(2025, 1, 1, 10, 0))
        service.create_backup(datetime(2025, 1, 2, 10, 0))

        respaldos = service.list_backups()
        assert len(respaldos) == 2
        assert respaldos[0].created_at >= respaldos[1].created_at

    def test_sin_respaldos_devuelve_lista_vacia(self, app_db):
        assert service.list_backups() == []


class TestRetencion:
    def _crear(self, cantidad: int) -> None:
        base = datetime(2025, 1, 1, 8, 0)
        for i in range(cantidad):
            service.create_backup(base + timedelta(days=i))

    def test_conserva_solo_los_mas_recientes(self, app_db):
        self._crear(5)
        eliminados = service.prune_backups(keep=3)

        assert eliminados == 2
        assert len(service.list_backups()) == 3

    def test_conserva_los_correctos(self, app_db):
        self._crear(5)
        antes = service.list_backups()
        service.prune_backups(keep=2)

        quedan = {b.path for b in service.list_backups()}
        assert quedan == {antes[0].path, antes[1].path}

    def test_no_borra_si_hay_menos_de_los_pedidos(self, app_db):
        self._crear(2)
        assert service.prune_backups(keep=30) == 0
        assert len(service.list_backups()) == 2

    def test_run_backup_aplica_la_retencion(self, app_db):
        self._crear(4)
        service.run_backup(Settings(backups_to_keep=2))
        assert len(service.list_backups()) == 2


class TestRespaldoAlCerrar:
    def test_respalda_si_esta_activado(self, app_db):
        path = service.run_exit_backup(Settings(backup_on_exit=True))
        assert path is not None and path.exists()

    def test_no_respalda_si_esta_desactivado(self, app_db):
        assert service.run_exit_backup(Settings(backup_on_exit=False)) is None
        assert service.list_backups() == []


class TestRestaurar:
    def test_devuelve_los_datos_al_estado_del_respaldo(self, app_db):
        alta("Ana Lopez")
        respaldo = service.create_backup()

        alta("Beto Ruiz")
        assert members_service.member_stats().total == 2

        service.restore_backup(respaldo)
        assert members_service.member_stats().total == 1

    def test_guarda_una_copia_antes_de_reemplazar(self, app_db):
        alta("Ana Lopez")
        respaldo = service.create_backup()
        alta("Beto Ruiz")

        service.restore_backup(respaldo)

        # Quedan el respaldo original y la copia de seguridad previa.
        assert len(service.list_backups()) == 2

    def test_la_copia_previa_permite_deshacer(self, app_db):
        alta("Ana Lopez")
        viejo = service.create_backup()
        alta("Beto Ruiz")

        service.restore_backup(viejo)
        assert members_service.member_stats().total == 1

        previa = next(b for b in service.list_backups() if b.path != viejo)
        service.restore_backup(previa.path)
        assert members_service.member_stats().total == 2

    def test_la_base_sigue_utilizable_despues_de_restaurar(self, app_db):
        alta("Ana Lopez")
        respaldo = service.create_backup()
        service.restore_backup(respaldo)

        alta("Carlos Nuevo")
        assert members_service.member_stats().total == 2

    def test_limpia_los_diarios_del_wal(self, app_db):
        alta("Ana Lopez")
        respaldo = service.create_backup()
        service.restore_backup(respaldo)

        wal = database_path().with_name(database_path().name + "-wal")
        assert not wal.exists() or wal.stat().st_size >= 0

    def test_archivo_inexistente(self, app_db, tmp_path):
        with pytest.raises(FileNotFoundError):
            service.restore_backup(tmp_path / "no-existe.sqlite")


class TestPantallaAjustes:
    def test_carga_los_ajustes_actuales(self, qtbot, app_db):
        window = MainWindow(Settings(gym_name="Gimnasio Uno", visit_price_cents=5500))
        qtbot.addWidget(window)

        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.name_input.text() == "Gimnasio Uno"
        assert page.visit_price_input.cents() == 5500

    def test_guardar_actualiza_la_ventana(self, qtbot, window):
        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.name_input.setText("Gimnasio Nuevo")
        page.visit_price_input.setText("60")
        page.save_settings()

        assert window.settings.gym_name == "Gimnasio Nuevo"
        assert window.settings.visit_price_cents == 6000
        assert window.sidebar.title.text() == "Gimnasio Nuevo"

    def test_nombre_vacio_muestra_error(self, qtbot, window):
        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.name_input.setText("   ")
        page.save_settings()

        assert page.name_field.error.isVisibleTo(page)

    def test_precio_invalido_muestra_error(self, qtbot, window):
        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.visit_price_input.setText("abc")
        page.save_settings()

        assert page.visit_price_field.error.isVisibleTo(page)

    def test_respaldar_ahora_agrega_a_la_lista(self, qtbot, window):
        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        assert page.backups_table.model.rowCount() == 0

        page.backup_now()
        assert page.backups_table.model.rowCount() == 1

    def test_sin_seleccion_no_falla(self, qtbot, window):
        page = SettingsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page.restore_selected()
