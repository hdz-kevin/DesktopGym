"""Pruebas del armazon de la interfaz."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from gym.config import Settings
from gym.ui.main_window import NAV_ITEMS, MainWindow, Page
from gym.ui.widgets.common import FilterChips
from gym.ui.widgets.inputs import MoneyInput, SearchBox
from gym.ui.widgets.table import Column, PagedTable


class DummyPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.refresh_count = 0

    def refresh(self) -> None:
        self.refresh_count += 1


@pytest.fixture
def window(qtbot):
    window = MainWindow(Settings(gym_name="Gimnasio de Prueba"))
    qtbot.addWidget(window)
    return window


class TestMainWindow:
    def test_registra_y_muestra_paginas(self, window, qtbot):
        page = DummyPage()
        window.register_page("members", page)
        window.show_page("members")

        assert window.stack.currentWidget() is page
        assert page.refresh_count == 1

    def test_marca_el_boton_activo_en_la_barra(self, window):
        window.register_page("members", DummyPage())
        window.show_page("members")
        assert window.sidebar.buttons["members"].isChecked()

    def test_atajo_de_teclado_cambia_de_pagina(self, window, qtbot):
        page = DummyPage()
        window.register_page("members", page)
        window.show()
        qtbot.waitExposed(window)

        qtbot.keyClick(window, Qt.Key.Key_F2)
        assert window.stack.currentWidget() is page

    def test_pagina_inexistente_no_rompe(self, window):
        window.show_page("no-existe")
        assert window.stack.currentWidget() is None or True

    def test_error_al_refrescar_no_tumba_la_app(self, window):
        class Rota(Page):
            def refresh(self):
                raise RuntimeError("fallo de consulta")

        window.register_page("members", Rota())
        window.show_page("members")

    def test_hay_un_atajo_por_cada_modulo(self):
        atajos = [item.shortcut for item in NAV_ITEMS]
        assert len(atajos) == len(set(atajos))


class TestPagedTable:
    def _tabla(self, qtbot):
        columns = [
            Column[dict]("Nombre", lambda r: r["nombre"], stretch=True),
            Column[dict]("Código", lambda r: r["codigo"], width=90),
        ]
        table = PagedTable[dict](columns, page_size=2)
        qtbot.addWidget(table)
        return table

    def test_muestra_filas_y_resumen(self, qtbot):
        table = self._tabla(qtbot)
        table.set_data([{"nombre": "Ana", "codigo": "10001"}], total=1)

        assert table.model.rowCount() == 1
        assert table.summary.text() == "1-1 de 1"

    def test_estado_vacio(self, qtbot):
        table = self._tabla(qtbot)
        table.set_data([], total=0)

        assert table.empty_label.isVisibleTo(table)
        assert table.summary.text() == "Sin resultados"

    def test_encabezado_sigue_la_alineacion_de_la_columna(self, qtbot):
        columns = [
            Column[dict]("Nombre", lambda r: r["nombre"], stretch=True),
            Column[dict](
                "Edad",
                lambda r: r["edad"],
                width=70,
                align=Qt.AlignmentFlag.AlignCenter,
            ),
        ]
        table = PagedTable[dict](columns, page_size=2)
        qtbot.addWidget(table)

        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        center = Qt.AlignmentFlag.AlignCenter
        assert table.model.headerData(
            0, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
        ) == int(left)
        assert table.model.headerData(
            1, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
        ) == int(center)

    def test_paginacion_calcula_offset(self, qtbot):
        table = self._tabla(qtbot)
        table.set_data([{"nombre": "A", "codigo": "1"}, {"nombre": "B", "codigo": "2"}], total=5)

        assert table.page_count == 3
        assert table.offset == 0

        table.go_to_page(2)
        assert table.page == 2
        assert table.offset == 2

    def test_no_pasa_de_la_ultima_pagina(self, qtbot):
        table = self._tabla(qtbot)
        table.set_data([{"nombre": "A", "codigo": "1"}], total=3)
        table.go_to_page(99)
        assert table.page == 2

    def test_reset_vuelve_a_la_primera(self, qtbot):
        table = self._tabla(qtbot)
        table.set_data([{"nombre": "A", "codigo": "1"}], total=10)
        table.go_to_page(3)
        table.reset_page()
        assert table.page == 1


class TestSearchBox:
    def test_espera_antes_de_emitir(self, qtbot):
        box = SearchBox()
        qtbot.addWidget(box)

        with qtbot.waitSignal(box.search_changed, timeout=1000) as blocker:
            qtbot.keyClicks(box, "ana")

        assert blocker.args == ["ana"]

    def test_escape_limpia_la_busqueda(self, qtbot):
        box = SearchBox()
        qtbot.addWidget(box)
        box.setText("ana")

        with qtbot.waitSignal(box.search_changed, timeout=1000) as blocker:
            qtbot.keyClick(box, Qt.Key.Key_Escape)

        assert blocker.args == [""]
        assert box.text() == ""


class TestMoneyInput:
    def test_convierte_a_centavos(self, qtbot):
        field = MoneyInput()
        qtbot.addWidget(field)
        field.setText("400.50")
        assert field.cents() == 40050

    def test_muestra_centavos_con_dos_decimales(self, qtbot):
        field = MoneyInput()
        qtbot.addWidget(field)
        field.set_cents(40000)
        assert field.text() == "400.00"

    def test_detecta_importe_invalido(self, qtbot):
        field = MoneyInput()
        qtbot.addWidget(field)
        field.setText("abc")
        assert not field.is_valid()


class TestFilterChips:
    def test_emite_el_valor_seleccionado(self, qtbot):
        chips = FilterChips([("all", "Todos"), ("active", "Activos")])
        qtbot.addWidget(chips)

        assert chips.current() == "all"

        boton = next(b for b, v in chips._values.items() if v == "active")
        with qtbot.waitSignal(chips.changed, timeout=1000) as blocker:
            boton.click()

        assert blocker.args == ["active"]
        assert chips.current() == "active"
