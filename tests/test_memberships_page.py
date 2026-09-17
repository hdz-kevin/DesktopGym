"""Pruebas de cobro, historial de pagos y catalogo de precios."""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from gym.config import Settings
from gym.domain.dates import format_range, humanize_delta
from gym.domain.enums import DurationUnit, MemberGender, MemberStatus
from gym.services import members as members_service
from gym.services import payments as payments_service
from gym.services import plans as service
from gym.ui.dialogs.charge_form import ChargeDialog
from gym.ui.dialogs.payment_history import PaymentHistoryDialog
from gym.ui.main_window import MainWindow
from gym.ui.pages.members import MembersPage
from gym.ui.pages.plans import PlanCategoryDialog, PlanDialog, PlansPage
from tests.conftest import default_category_id


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez") -> int:
    return members_service.create_member(
        members_service.MemberForm(
            name=nombre,
            gender=MemberGender.FEMALE,
            plan_category_id=default_category_id(),
        )
    )


class TestMembersChargePage:
    def test_lista_socios_con_plan(self, qtbot, window, app_catalog):
        payments_service.charge(alta("Ana Lopez"), app_catalog["monthly_id"])
        payments_service.charge(alta("Beto Ruiz"), app_catalog["monthly_id"])

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 2
        assert page.stat_active.value_label.text() == "2"
        assert page.table.model.headerData(3, Qt.Orientation.Horizontal) == "Plan"
        assert (
            page.table.model.data(page.table.model.index(0, 3), Qt.ItemDataRole.DisplayRole)
            == "Mensual"
        )

    def test_vigencia_es_tiempo_relativo(self, qtbot, window, app_catalog):
        payments_service.charge(alta("Vigente"), app_catalog["monthly_id"])
        payments_service.charge(alta("Vencida"), app_catalog["monthly_id"], start=date(2020, 1, 1))

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        for fila in range(page.table.model.rowCount()):
            socio = page.table.model.record_at(fila)
            texto = page.table.model.data(
                page.table.model.index(fila, 4), Qt.ItemDataRole.DisplayRole
            )
            pago = socio.recent_payment
            delta = humanize_delta(pago.end_date)
            esperado = f"en {delta}" if socio.status is MemberStatus.ACTIVE else f"hace {delta}"
            assert texto == esperado

    def test_filtra_por_vencidos(self, qtbot, window, app_catalog):
        payments_service.charge(alta("Vigente"), app_catalog["monthly_id"])
        payments_service.charge(alta("Vencida"), app_catalog["monthly_id"], start=date(2020, 1, 1))

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter(MemberStatus.EXPIRED)

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Vencida"

    def test_busca_por_socio(self, qtbot, window, app_catalog):
        payments_service.charge(alta("Ana Lopez"), app_catalog["monthly_id"])
        payments_service.charge(alta("Beto Ruiz"), app_catalog["monthly_id"])

        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_search("beto")

        assert page.table.model.rowCount() == 1

    def test_avisa_si_la_categoria_no_tiene_planes(self, qtbot, app_db):
        window = MainWindow(Settings())
        qtbot.addWidget(window)
        member_id = alta()
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page.table.view.selectRow(0)

        page.charge_selected()
        assert not members_service.get_member(member_id).payments

    def test_sin_seleccion_no_falla(self, qtbot, window, app_catalog):
        page = MembersPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.charge_selected()
        page.show_history()


class TestChargeDialog:
    def test_registra_el_pago(self, qtbot, window, app_catalog):
        member = members_service.get_member(alta())
        dialog = ChargeDialog(member, window)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert len(members_service.get_member(member.id).payments) == 1

    def test_muestra_la_vista_previa_de_vigencia(self, qtbot, window, app_catalog):
        dialog = ChargeDialog(members_service.get_member(alta()), window)
        qtbot.addWidget(dialog)

        assert "Vigencia:" in dialog.preview.text()
        assert "Importe:" in dialog.preview.text()

    def test_sugiere_continuar_tras_el_vencimiento(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        member = members_service.get_member(member_id)

        dialog = ChargeDialog(member, window)
        qtbot.addWidget(dialog)

        from datetime import timedelta

        esperado = member.recent_payment.end_date.date() + timedelta(days=1)
        qdate = dialog.start_input.date()
        assert date(qdate.year(), qdate.month(), qdate.day()) == esperado

    def test_cobrar_de_nuevo_agrega_un_periodo(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        dialog = ChargeDialog(members_service.get_member(member_id), window)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert len(members_service.get_member(member_id).payments) == 2

    def test_precarga_el_plan_actual(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        dialog = ChargeDialog(members_service.get_member(member_id), window)
        qtbot.addWidget(dialog)

        assert dialog.plan_input.currentData() == app_catalog["monthly_id"]


class TestHistoryDialog:
    def test_muestra_los_pagos(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["monthly_id"])

        dialog = PaymentHistoryDialog(member_id, window)
        qtbot.addWidget(dialog)

        assert dialog.table.model.rowCount() == 2
        assert dialog.payments_value.text() == "2"
        assert dialog.total_value.text().startswith("$")
        nombres = [
            label.text()
            for label in dialog.findChildren(QLabel)
            if label.objectName() == "memberName"
        ]
        assert nombres == ["Ana Lopez"]
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

    def test_pagina_a_partir_de_30_pagos(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        for _ in range(30):
            payments_service.charge(member_id, app_catalog["monthly_id"])

        dialog = PaymentHistoryDialog(member_id, window)
        qtbot.addWidget(dialog)

        assert dialog.payments_value.text() == "31"
        assert dialog.table.model.rowCount() == 30
        assert dialog.table.pager.isVisibleTo(dialog)

        dialog.table.go_to_page(2)
        assert dialog.table.model.rowCount() == 1


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
