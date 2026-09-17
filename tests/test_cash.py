"""Pruebas del corte de caja."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from gym.config import Settings
from gym.data.database import session_scope
from gym.data.models import Payment
from gym.services import cash as service
from gym.services import members as members_service
from gym.services import payments as payments_service
from gym.services import products as products_service
from gym.services import sales as sales_service
from gym.services import visits as visits_service
from gym.services.sales import Cart
from gym.services.visits import VisitRange
from gym.ui.main_window import MainWindow
from gym.ui.pages.cash import CashPage
from tests.conftest import default_category_id


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def alta(nombre="Ana Lopez") -> int:
    return members_service.create_member(
        members_service.MemberForm(
            name=nombre,
            plan_category_id=default_category_id(),
        )
    )


def vender(precio=1500, cantidad=1, cuando=None) -> None:
    product_id = products_service.create_product(
        products_service.ProductForm(name=f"Producto {precio}", price_cents=precio, stock=100)
    )
    cart = Cart()
    cart.add(products_service.get_product(product_id), cantidad)
    sales_service.checkout(cart, sold_at=cuando)


def antedatar_pagos(dias: int) -> None:
    """Mueve al pasado la fecha de registro de todos los pagos."""
    with session_scope() as session:
        for payment in session.query(Payment).all():
            payment.created_at = datetime.now() - timedelta(days=dias)


class TestReporte:
    def test_sin_movimientos_todo_en_cero(self, app_db):
        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.total_revenue_cents == 0
        assert reporte.transaction_count == 0

    def test_suma_las_visitas(self, app_db):
        visits_service.create_visit(4000)
        visits_service.create_visit(2500)

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.visits.count == 2
        assert reporte.visits.revenue_cents == 6500

    def test_suma_las_ventas(self, app_db):
        vender(precio=1500, cantidad=2)

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.sales.count == 1
        assert reporte.sales.revenue_cents == 3000

    def test_un_alta_cuenta_como_nueva(self, app_db, app_catalog):
        payments_service.charge(alta(), app_catalog["monthly_id"])

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.new_memberships.count == 1
        assert reporte.new_memberships.revenue_cents == 40000
        assert reporte.renewals.count == 0

    def test_el_segundo_pago_cuenta_como_renovacion(self, app_db, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["biweekly_id"])

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.new_memberships.count == 1
        assert reporte.new_memberships.revenue_cents == 40000
        assert reporte.renewals.count == 1
        assert reporte.renewals.revenue_cents == 25000

    def test_varias_renovaciones(self, app_db, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["monthly_id"])

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.new_memberships.count == 1
        assert reporte.renewals.count == 2

    def test_dos_socios_distintos_son_dos_altas(self, app_db, app_catalog):
        payments_service.charge(alta("Ana"), app_catalog["monthly_id"])
        payments_service.charge(alta("Beto"), app_catalog["monthly_id"])

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.new_memberships.count == 2
        assert reporte.renewals.count == 0

    def test_total_suma_todos_los_conceptos(self, app_db, app_catalog):
        visits_service.create_visit(4000)
        vender(precio=1500, cantidad=2)
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["biweekly_id"])

        reporte = service.build_report(VisitRange.TODAY)

        assert reporte.memberships_revenue_cents == 65000
        assert reporte.total_revenue_cents == 4000 + 3000 + 65000
        assert reporte.transaction_count == 1 + 1 + 1 + 1

    def test_lo_de_hoy_no_incluye_lo_viejo(self, app_db, app_catalog):
        visits_service.create_visit(4000, datetime.now() - timedelta(days=40))
        vender(cuando=datetime.now() - timedelta(days=40))
        payments_service.charge(alta(), app_catalog["monthly_id"])
        antedatar_pagos(40)

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.total_revenue_cents == 0

    def test_el_mes_incluye_lo_de_hoy(self, app_db):
        visits_service.create_visit(4000)
        assert service.build_report(VisitRange.MONTH).visits.count == 1

    def test_la_semana_va_de_lunes_a_domingo(self, app_db):
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        visits_service.create_visit(
            4000, datetime.combine(lunes, datetime.min.time().replace(hour=10))
        )
        visits_service.create_visit(
            4000, datetime.combine(lunes - timedelta(days=1), datetime.min.time().replace(hour=10))
        )

        assert service.build_report(VisitRange.WEEK).visits.count == 1

    def test_desglose_diario(self, app_db):
        visits_service.create_visit(4000)
        vender(precio=1500)

        desglose = service.daily_breakdown(VisitRange.MONTH)
        assert len(desglose) >= 1
        assert sum(total for _, total in desglose) == 5500

    def test_una_venta_anulada_no_entra_al_corte(self, app_db):
        product_id = products_service.create_product(
            products_service.ProductForm(name="Agua", price_cents=1500, stock=10)
        )
        cart = Cart()
        cart.add(products_service.get_product(product_id), 2)
        sale_id = sales_service.checkout(cart)
        sales_service.void_sale(sale_id)

        reporte = service.build_report(VisitRange.TODAY)
        assert reporte.sales.count == 0
        assert reporte.sales.revenue_cents == 0
        assert reporte.total_revenue_cents == 0
        assert service.daily_breakdown(VisitRange.TODAY) == []


class TestPantalla:
    def test_muestra_los_totales(self, qtbot, window, app_catalog):
        visits_service.create_visit(4000)
        payments_service.charge(alta(), app_catalog["monthly_id"])

        page = CashPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.stat_total.value_label.text() == "$440.00"
        assert page.stat_payments.value_label.text() == "$400.00"
        assert page.stat_visits.value_label.text() == "$40.00"

    def test_distingue_altas_de_renovaciones(self, qtbot, window, app_catalog):
        member_id = alta()
        payments_service.charge(member_id, app_catalog["monthly_id"])
        payments_service.charge(member_id, app_catalog["biweekly_id"])

        page = CashPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert "1 alta(s)" in page.row_new.count_label.text()
        assert "1 renovación(es)" in page.row_renewals.count_label.text()
        assert page.row_renewals.amount_label.text() == "$250.00"

    def test_muestra_los_mas_vendidos(self, qtbot, window):
        vender(precio=1500, cantidad=3)

        page = CashPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.top_table.model.rowCount() == 1

    def test_cambiar_de_periodo(self, qtbot, window):
        visits_service.create_visit(4000, datetime.now() - timedelta(days=40))

        page = CashPage(window)
        qtbot.addWidget(page)
        page.refresh()
        assert page.stat_total.value_label.text() == "$0.00"

        page._on_range(VisitRange.MONTH)
        assert page.stat_total.value_label.text() == "$0.00"

    def test_sin_datos_no_falla(self, qtbot, window):
        page = CashPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.stat_total.value_label.text() == "$0.00"
        assert page.top_table.model.rowCount() == 0
