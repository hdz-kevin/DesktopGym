"""Pruebas de las pantallas de membresias y precios."""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from gym.config import Settings
from gym.domain.dates import format_date, format_range, humanize_delta
from gym.domain.enums import DurationUnit, MemberGender, MembershipStatus
from gym.services import members as members_service
from gym.services import memberships as service
from gym.ui.dialogs.membership_form import MembershipFormDialog, RenewMembershipDialog
from gym.ui.dialogs.membership_history import MembershipHistoryDialog
from gym.ui.main_window import MainWindow
from gym.ui.pages.memberships import MembershipsPage
from gym.ui.pages.plans import PlanCategoryDialog, PlanDialog, PlansPage


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez") -> int:
    return members_service.create_member(
        members_service.MemberForm(name=nombre, gender=MemberGender.FEMALE)
    )


class TestMembershipsPage:
    def test_lista_las_membresias(self, qtbot, window, app_catalog):
        service.create_membership(alta("Ana Lopez"), app_catalog["monthly_id"])
        service.create_membership(alta("Beto Ruiz"), app_catalog["monthly_id"])

        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 2
        assert page.stat_active.value_label.text() == "2"
        assert page.table.model.headerData(2, Qt.Orientation.Horizontal) == "Plan"
        assert (
            page.table.model.data(page.table.model.index(0, 2), Qt.ItemDataRole.DisplayRole)
            == "General · Mensual"
        )

    def test_vigencia_es_tiempo_relativo(self, qtbot, window, app_catalog):
        service.create_membership(alta("Vigente"), app_catalog["monthly_id"])
        service.create_membership(
            alta("Vencida"), app_catalog["monthly_id"], start=date(2020, 1, 1)
        )

        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        for fila in range(page.table.model.rowCount()):
            membresia = page.table.model.record_at(fila)
            texto = page.table.model.data(
                page.table.model.index(fila, 3), Qt.ItemDataRole.DisplayRole
            )
            pago = membresia.recent_payment
            delta = humanize_delta(pago.end_date)
            if membresia.status is MembershipStatus.ACTIVE:
                esperado = f"en {delta}"
            else:
                esperado = f"hace {delta}"
            assert texto == esperado
            assert format_date(pago.end_date) not in texto

    def test_filtra_por_vencidas(self, qtbot, window, app_catalog):
        service.create_membership(alta("Vigente"), app_catalog["monthly_id"])
        service.create_membership(
            alta("Vencida"), app_catalog["monthly_id"], start=date(2020, 1, 1)
        )

        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter(MembershipStatus.EXPIRED)

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).member.name == "Vencida"

    def test_busca_por_socio(self, qtbot, window, app_catalog):
        service.create_membership(alta("Ana Lopez"), app_catalog["monthly_id"])
        service.create_membership(alta("Beto Ruiz"), app_catalog["monthly_id"])

        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_search("beto")

        assert page.table.model.rowCount() == 1

    def test_avisa_si_no_hay_planes(self, qtbot, app_db):
        window = MainWindow(Settings())
        qtbot.addWidget(window)
        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.create_membership()
        assert page.table.model.rowCount() == 0

    def test_sin_seleccion_no_falla(self, qtbot, window, app_catalog):
        page = MembershipsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.renew_selected()


class TestMembershipFormDialog:
    def test_requiere_socio(self, qtbot, window, app_catalog):
        dialog = MembershipFormDialog(window)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert dialog.membership_id is None
        assert dialog.member_field.error.isVisibleTo(dialog)

    def test_registra_la_membresia(self, qtbot, window, app_catalog):
        member_id = alta()
        dialog = MembershipFormDialog(window, member_id=member_id)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert dialog.membership_id is not None
        membership = service.get_membership(dialog.membership_id)
        assert membership.member_id == member_id
        assert len(membership.payments) == 1

    def test_muestra_la_vista_previa_de_vigencia(self, qtbot, window, app_catalog):
        dialog = MembershipFormDialog(window, member_id=alta())
        qtbot.addWidget(dialog)

        assert "Vigencia:" in dialog.preview.text()
        assert "Importe:" in dialog.preview.text()

    def test_el_buscador_encuentra_socios(self, qtbot, window, app_catalog):
        alta("Ana Lopez")
        dialog = MembershipFormDialog(window)
        qtbot.addWidget(dialog)

        assert not dialog.results.isVisibleTo(dialog)

        dialog._search_members("ana")

        assert dialog.results.count() == 1
        assert dialog.results.isVisibleTo(dialog)


class TestRenewDialog:
    def test_sugiere_continuar_tras_el_vencimiento(self, qtbot, window, app_catalog):
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])
        membership = service.get_membership(membership_id)

        dialog = RenewMembershipDialog(membership, window)
        qtbot.addWidget(dialog)

        from datetime import timedelta

        esperado = membership.recent_payment.end_date.date() + timedelta(days=1)
        qdate = dialog.start_input.date()
        assert date(qdate.year(), qdate.month(), qdate.day()) == esperado

    def test_renovar_agrega_un_periodo(self, qtbot, window, app_catalog):
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])
        dialog = RenewMembershipDialog(service.get_membership(membership_id), window)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert len(service.get_membership(membership_id).payments) == 2

    def test_precarga_el_plan_actual(self, qtbot, window, app_catalog):
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])
        dialog = RenewMembershipDialog(service.get_membership(membership_id), window)
        qtbot.addWidget(dialog)

        assert dialog.plan_input.currentData() == app_catalog["monthly_id"]


class TestHistoryDialog:
    def test_muestra_los_pagos(self, qtbot, window, app_catalog):
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])
        service.renew_membership(membership_id, app_catalog["monthly_id"])

        dialog = MembershipHistoryDialog(membership_id, window)
        qtbot.addWidget(dialog)

        assert dialog.table.model.rowCount() == 2
        assert dialog.payments_value.text() == "2"
        assert dialog.total_value.text().startswith("$")
        titulos = [
            label.text()
            for label in dialog.findChildren(QLabel)
            if label.objectName() == "pageTitle"
        ]
        assert titulos == ["Membresía de Ana Lopez"]
        planes = [
            dialog.table.model.data(dialog.table.model.index(i, 1), Qt.ItemDataRole.DisplayRole)
            for i in range(2)
        ]
        assert planes == ["General · Mensual", "General · Mensual"]
        etiquetas = [
            dialog.table.model.data(dialog.table.model.index(i, 3), Qt.ItemDataRole.DisplayRole)
            for i in range(2)
        ]
        assert etiquetas.count("Vigente") == 1
        vigencia = dialog.table.model.data(
            dialog.table.model.index(0, 0), Qt.ItemDataRole.DisplayRole
        )
        pago = dialog.table.model.record_at(0)
        assert vigencia == format_range(pago.start_date, pago.end_date)


class TestPlansPage:
    def test_muestra_categorias_y_planes(self, qtbot, window, app_catalog):
        page = PlansPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.categories_table.model.rowCount() == 1
        assert page.plans_table.model.rowCount() == 2

    def test_crear_categoria(self, qtbot, window, app_catalog):
        dialog = PlanCategoryDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Premium")
        dialog.accept()

        assert len(service.list_plan_categories()) == 2

    def test_categoria_duplicada_muestra_error(self, qtbot, window, app_catalog):
        dialog = PlanCategoryDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("General")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.name_field.error.isVisibleTo(dialog)

    def test_crear_plan(self, qtbot, window, app_catalog):
        dialog = PlanDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Trimestral")
        dialog.amount_input.setValue(3)
        dialog.unit_input.setCurrentIndex(dialog.unit_input.findData(DurationUnit.MONTH.value))
        dialog.price_input.setText("1000")
        dialog.accept()

        assert len(service.list_plans()) == 3

    def test_plan_con_precio_invalido(self, qtbot, window, app_catalog):
        dialog = PlanDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Trimestral")
        dialog.price_input.setText("abc")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.price_field.error.isVisibleTo(dialog)

    def test_editar_plan_precarga_datos(self, qtbot, window, app_catalog):
        plan = next(d for d in service.list_plans() if d.id == app_catalog["monthly_id"])
        dialog = PlanDialog(window, plan)
        qtbot.addWidget(dialog)

        assert dialog.name_input.text() == "Mensual"
        assert dialog.price_input.cents() == 40000
        assert not dialog.category_input.isEnabled()

    def test_sin_seleccion_no_falla(self, qtbot, window, app_catalog):
        page = PlansPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.edit_category()
        page.delete_category()
        page.edit_plan()
        page.delete_plan()
