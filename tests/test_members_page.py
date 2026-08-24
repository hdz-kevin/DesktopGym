"""Pruebas de las pantallas de socios y kiosco."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt

from gym.config import Settings
from gym.data.database import session_scope
from gym.data.models import Membership, Period
from gym.domain.enums import MemberGender, MemberStatus
from gym.services import members as service
from gym.ui.dialogs.member_form import MemberFormDialog
from gym.ui.dialogs.member_profile import MemberProfileDialog
from gym.ui.main_window import MainWindow
from gym.ui.pages.kiosk import KioskPage
from gym.ui.pages.members import MembersPage


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez", gender=MemberGender.FEMALE) -> int:
    return service.create_member(service.MemberForm(name=nombre, gender=gender))


def dar_periodo(member_id: int, catalog: dict, dias: int) -> None:
    ahora = datetime.now()
    with session_scope() as session:
        membership = Membership(member_id=member_id, membership_type_id=catalog["type_id"])
        session.add(membership)
        session.flush()
        session.add(
            Period(
                membership_id=membership.id,
                duration_id=catalog["monthly_id"],
                start_date=ahora - timedelta(days=30),
                end_date=ahora + timedelta(days=dias),
                price_paid_cents=40000,
            )
        )


class TestMembersPage:
    def test_muestra_los_socios(self, qtbot, window):
        alta("Ana Lopez")
        alta("Beto Ruiz")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 2

    def test_estadisticas_reflejan_los_estados(self, qtbot, window, app_catalog):
        activo = alta("Activo")
        alta("Sin membresia")
        dar_periodo(activo, app_catalog, dias=10)

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.stat_total.value_label.text() == "2"
        assert page.stat_active.value_label.text() == "1"
        assert page.stat_none.value_label.text() == "1"

    def test_filtrar_por_activos(self, qtbot, window, app_catalog):
        activo = alta("Activo Ramirez")
        alta("Nuevo Sanchez")
        dar_periodo(activo, app_catalog, dias=10)

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter(MemberStatus.ACTIVE)

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Activo Ramirez"

    def test_buscar_por_nombre(self, qtbot, window):
        alta("Ana Lopez")
        alta("Beto Ruiz")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_search("beto")

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Beto Ruiz"

    def test_buscar_vuelve_a_la_primera_pagina(self, qtbot, window):
        for i in range(30):
            alta(f"Socio {i:02d}")

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page.table.go_to_page(2)
        assert page.table.page == 2

        page._on_search("Socio 0")
        assert page.table.page == 1

    def test_sin_seleccion_avisa_en_vez_de_fallar(self, qtbot, window):
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.edit_selected()
        page.delete_selected()
        page.open_profile()

    def test_estado_vacio(self, qtbot, window):
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 0
        assert page.table.summary.text() == "Sin resultados"


class TestMemberFormDialog:
    def test_guarda_un_socio_nuevo(self, qtbot, window):
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Carlos Mendez")
        dialog.accept()

        assert dialog.member_id is not None
        assert service.get_member(dialog.member_id).name == "Carlos Mendez"

    def test_muestra_error_en_el_campo_invalido(self, qtbot, window):
        dialog = MemberFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Ab")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.name_field.error.isVisibleTo(dialog)
        assert "3 caracteres" in dialog.name_field.error.text()

    def test_precarga_los_datos_al_editar(self, qtbot, window):
        member_id = alta("Ana Lopez")
        member = service.get_member(member_id)

        dialog = MemberFormDialog(window, member)
        qtbot.addWidget(dialog)

        assert dialog.name_input.text() == "Ana Lopez"
        assert dialog.build_form().gender is MemberGender.FEMALE

    def test_editar_conserva_el_codigo(self, qtbot, window):
        member_id = alta("Ana Lopez")
        codigo = service.get_member(member_id).code

        dialog = MemberFormDialog(window, service.get_member(member_id))
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Ana Maria Lopez")
        dialog.accept()

        actualizado = service.get_member(member_id)
        assert actualizado.name == "Ana Maria Lopez"
        assert actualizado.code == codigo


class TestMemberProfileDialog:
    def test_abre_para_socio_sin_membresia(self, qtbot, window):
        member = service.get_member(alta())
        dialog = MemberProfileDialog(member, window)
        qtbot.addWidget(dialog)

    def test_abre_para_socio_con_membresia(self, qtbot, window, app_catalog):
        member_id = alta()
        dar_periodo(member_id, app_catalog, dias=10)
        dialog = MemberProfileDialog(service.get_member(member_id), window)
        qtbot.addWidget(dialog)


class TestKioskPage:
    def _page(self, qtbot, window):
        page = KioskPage(window)
        qtbot.addWidget(page)
        page.refresh()
        return page

    def test_codigo_valido_da_bienvenida(self, qtbot, window, app_catalog):
        member_id = alta("Ana Lopez")
        dar_periodo(member_id, app_catalog, dias=10)
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_card.isVisibleTo(page)
        assert page.result_title.text() == "¡Bienvenido!"
        assert page.result_name.text() == "Ana Lopez"

    def test_membresia_vencida_niega_el_paso(self, qtbot, window, app_catalog):
        member_id = alta("Vencido Torres")
        dar_periodo(member_id, app_catalog, dias=-5)
        codigo = service.get_member(member_id).code

        page = self._page(qtbot, window)
        page.code_input.setText(codigo)

        assert page.result_title.text() == "Membresía vencida."
        assert "Venció el" in page.result_detail.text()

    def test_codigo_inexistente(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")

        assert "No encontramos" in page.result_title.text()

    def test_consulta_sola_al_completar_cinco_digitos(self, qtbot, window):
        page = self._page(qtbot, window)
        qtbot.keyClicks(page.code_input, "9999")
        assert not page.result_card.isVisibleTo(page)

        qtbot.keyClicks(page.code_input, "9")
        assert page.result_card.isVisibleTo(page)

    def test_limpia_el_campo_tras_consultar(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")
        assert page.code_input.text() == ""

    def test_teclear_de_nuevo_oculta_el_resultado(self, qtbot, window):
        page = self._page(qtbot, window)
        page.code_input.setText("99999")
        assert page.result_card.isVisibleTo(page)

        qtbot.keyClick(page.code_input, Qt.Key.Key_1)
        assert not page.result_card.isVisibleTo(page)
