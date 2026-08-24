from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from gym.config import Settings
from gym.services import visits as service
from gym.services.errors import NotFoundError, ValidationError
from gym.services.visits import VisitRange
from gym.ui.main_window import MainWindow
from gym.ui.pages.visits import VisitDialog, VisitsPage


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings(visit_price_cents=4000))
    qtbot.addWidget(window)
    return window


def hoy_a_las(hora: int = 12) -> datetime:
    return datetime.combine(date.today(), time(hora, 0))


class TestServicio:
    def test_registra_una_visita(self, app_db):
        service.create_visit(4000)
        rows, total = service.list_visits(VisitRange.TODAY)
        assert total == 1 and rows[0].price_cents == 4000

    def test_rechaza_precio_negativo(self, app_db):
        with pytest.raises(ValidationError):
            service.create_visit(-1)

    def test_admite_visita_gratuita(self, app_db):
        service.create_visit(0)
        assert service.totals(VisitRange.TODAY).count == 1

    def test_actualiza_una_visita(self, app_db):
        visit_id = service.create_visit(4000)
        nuevo_momento = hoy_a_las(9)
        service.update_visit(visit_id, 5000, nuevo_momento)

        rows, _ = service.list_visits(VisitRange.TODAY)
        assert rows[0].price_cents == 5000
        assert rows[0].visit_at.hour == 9

    def test_elimina_una_visita(self, app_db):
        visit_id = service.create_visit(4000)
        service.delete_visit(visit_id)
        assert service.totals(VisitRange.TODAY).count == 0

    def test_visita_inexistente(self, app_db):
        with pytest.raises(NotFoundError):
            service.delete_visit(999)

    def test_ordena_de_la_mas_reciente_a_la_mas_vieja(self, app_db):
        service.create_visit(4000, hoy_a_las(8))
        service.create_visit(5000, hoy_a_las(18))

        rows, _ = service.list_visits(VisitRange.TODAY)
        assert rows[0].price_cents == 5000


class TestFiltrosPorPeriodo:
    def _poblar(self):
        ahora = datetime.now()
        service.create_visit(4000, ahora)
        service.create_visit(4000, ahora - timedelta(days=40))

    def test_hoy_excluye_lo_viejo(self, app_db):
        self._poblar()
        assert service.totals(VisitRange.TODAY).count == 1

    def test_todas_incluye_el_historico(self, app_db):
        self._poblar()
        assert service.totals(VisitRange.ALL).count == 2

    def test_mes_incluye_lo_del_mes_en_curso(self, app_db):
        service.create_visit(4000, datetime.now())
        assert service.totals(VisitRange.MONTH).count == 1

    def test_semana_va_de_lunes_a_domingo(self, app_db):
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        service.create_visit(4000, datetime.combine(lunes, time(10, 0)))
        service.create_visit(4000, datetime.combine(lunes - timedelta(days=1), time(10, 0)))

        assert service.totals(VisitRange.WEEK).count == 1

    def test_suma_los_ingresos_del_periodo(self, app_db):
        service.create_visit(4000)
        service.create_visit(2500)
        assert service.totals(VisitRange.TODAY).revenue_cents == 6500

    def test_sin_visitas_los_totales_son_cero(self, app_db):
        totales = service.totals(VisitRange.TODAY)
        assert (totales.count, totales.revenue_cents) == (0, 0)

    def test_pagina_los_resultados(self, app_db):
        for _ in range(7):
            service.create_visit(4000)
        primera, total = service.list_visits(VisitRange.TODAY, offset=0, limit=5)
        segunda, _ = service.list_visits(VisitRange.TODAY, offset=5, limit=5)

        assert total == 7
        assert len(primera) == 5 and len(segunda) == 2


class TestPantalla:
    def test_muestra_las_visitas_de_hoy(self, qtbot, window):
        service.create_visit(4000)

        page = VisitsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 1
        assert page.stat_count.value_label.text() == "1"
        assert page.stat_revenue.value_label.text() == "$40.00"

    def test_cambiar_de_periodo(self, qtbot, window):
        service.create_visit(4000, datetime.now() - timedelta(days=40))

        page = VisitsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.model.rowCount() == 0

        page._on_range(VisitRange.ALL)
        assert page.table.model.rowCount() == 1

    def test_el_dialogo_usa_el_precio_configurado(self, qtbot, window):
        dialog = VisitDialog(window, default_price_cents=5500)
        qtbot.addWidget(dialog)
        assert dialog.price_input.cents() == 5500

    def test_registra_desde_el_dialogo(self, qtbot, window):
        dialog = VisitDialog(window, default_price_cents=4000)
        qtbot.addWidget(dialog)
        dialog.accept()

        assert service.totals(VisitRange.TODAY).count == 1

    def test_importe_invalido_muestra_error(self, qtbot, window):
        dialog = VisitDialog(window)
        qtbot.addWidget(dialog)
        dialog.price_input.setText("abc")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.price_field.error.isVisibleTo(dialog)

    def test_sin_seleccion_no_falla(self, qtbot, window):
        page = VisitsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.edit_selected()
        page.delete_selected()
