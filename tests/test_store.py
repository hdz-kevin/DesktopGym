"""Pruebas de productos, carrito, cobro y sus pantallas."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt

from gym.config import Settings
from gym.services import products as products_service
from gym.services import sales as service
from gym.services.errors import (
    InsufficientStockError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from gym.services.sales import Cart
from gym.services.visits import VisitRange
from gym.ui.dialogs.sale_detail import SaleDetailDialog
from gym.ui.main_window import MainWindow
from gym.ui.pages.products import ProductDialog, ProductsPage
from gym.ui.pages.sale_history import SalesHistoryPage
from gym.ui.pages.sales import SalesPage


@pytest.fixture
def window(qtbot, app_db):
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def producto(nombre="Agua", precio=1500, stock=10, activo=True) -> int:
    return products_service.create_product(
        products_service.ProductForm(name=nombre, price_cents=precio, stock=stock, is_active=activo)
    )


class TestCatalogo:
    def test_crea_un_producto(self, app_db):
        producto()
        rows, total = products_service.list_products()
        assert total == 1 and rows[0].name == "Agua"

    def test_rechaza_stock_nulo(self, app_db):
        with pytest.raises(ValidationError) as exc:
            producto(stock=None)
        assert "stock" in exc.value.errors

    def test_admite_stock_agotado(self, app_db):
        product_id = producto(stock=0)
        assert products_service.get_product(product_id).stock == 0

    @pytest.mark.parametrize(
        ("nombre", "precio", "stock", "campo"),
        [
            ("", 1500, 10, "name"),
            ("Agua", -1, 10, "price"),
            ("Agua", 1500, -5, "stock"),
            ("Agua", 1500, None, "stock"),
        ],
    )
    def test_valida_los_datos(self, app_db, nombre, precio, stock, campo):
        with pytest.raises(ValidationError) as exc:
            producto(nombre, precio, stock)
        assert campo in exc.value.errors

    def test_admite_producto_gratuito(self, app_db):
        product_id = producto(precio=0)
        assert products_service.get_product(product_id).price_cents == 0

    def test_activa_y_desactiva(self, app_db):
        product_id = producto()
        products_service.set_active(product_id, False)
        assert not products_service.get_product(product_id).is_active

    def test_filtra_solo_disponibles(self, app_db):
        producto("Agua", activo=True)
        producto("Barra", activo=False)

        _, total = products_service.list_products(only_active=True)
        assert total == 1

    def test_filtra_agotados(self, app_db):
        producto("Agua", stock=5)
        producto("Toalla", stock=0)

        rows, total = products_service.list_products(stock="out_of_stock")
        assert total == 1 and rows[0].name == "Toalla"

    def test_filtra_stock_bajo(self, app_db):
        producto("Agua", stock=5)
        producto("Toalla", stock=0)
        producto("Electrolit", stock=40)

        rows, total = products_service.list_products(stock="low_stock")
        assert total == 1 and rows[0].name == "Agua"

    def test_busca_por_nombre(self, app_db):
        producto("Agua natural")
        producto("Barra proteica")

        _, total = products_service.list_products(search="barra")
        assert total == 1

    def test_ajusta_el_inventario(self, app_db):
        product_id = producto(stock=10)
        assert products_service.adjust_stock(product_id, 5) == 15
        assert products_service.adjust_stock(product_id, -12) == 3

    def test_el_inventario_no_queda_negativo(self, app_db):
        product_id = producto(stock=3)
        with pytest.raises(ServiceError):
            products_service.adjust_stock(product_id, -10)

    def test_borra_un_producto_sin_ventas(self, app_db):
        product_id = producto()
        products_service.delete_product(product_id)
        with pytest.raises(NotFoundError):
            products_service.get_product(product_id)

    def test_no_borra_un_producto_vendido(self, app_db):
        product_id = producto()
        cart = Cart()
        cart.add(products_service.get_product(product_id), 1)
        service.checkout(cart)

        with pytest.raises(ServiceError, match="Desactívalo"):
            products_service.delete_product(product_id)

    def test_productos_vendibles_excluye_agotados_e_inactivos(self, app_db):
        producto("Disponible", stock=5)
        producto("Agotado", stock=0)
        producto("Desactivado", stock=5, activo=False)

        nombres = {p.name for p in products_service.sellable_products()}
        assert nombres == {"Disponible"}

    def test_stock_bajo(self, app_db):
        producto("Casi agotado", stock=2)
        producto("Con inventario", stock=50)
        producto("Agotado", stock=0)

        bajos = products_service.low_stock(threshold=5)
        assert [p.name for p in bajos] == ["Agotado", "Casi agotado"]


class TestCarrito:
    def test_agrega_y_suma(self, app_db):
        cart = Cart()
        cart.add(products_service.get_product(producto("Agua", 1500)), 2)

        assert cart.item_count == 2
        assert cart.total_cents == 3000

    def test_agregar_dos_veces_acumula(self, app_db):
        product = products_service.get_product(producto("Agua", 1500))
        cart = Cart()
        cart.add(product, 1)
        cart.add(product, 2)

        assert len(cart.lines) == 1
        assert cart.item_count == 3

    def test_no_pasa_del_stock_disponible(self, app_db):
        product = products_service.get_product(producto("Agua", 1500, stock=3))
        cart = Cart()

        with pytest.raises(InsufficientStockError, match="Quedan 3"):
            cart.add(product, 4)

    def test_acumular_tampoco_pasa_del_stock(self, app_db):
        product = products_service.get_product(producto("Agua", stock=3))
        cart = Cart()
        cart.add(product, 2)

        with pytest.raises(InsufficientStockError):
            cart.add(product, 2)

    def test_cambiar_cantidad_a_cero_quita_la_linea(self, app_db):
        product_id = producto("Agua")
        cart = Cart()
        cart.add(products_service.get_product(product_id), 3)
        cart.set_quantity(product_id, 0)

        assert cart.is_empty

    def test_rechaza_cantidad_no_positiva(self, app_db):
        product = products_service.get_product(producto())
        cart = Cart()
        with pytest.raises(ValidationError):
            cart.add(product, 0)

    def test_vaciar_el_carrito(self, app_db):
        cart = Cart()
        cart.add(products_service.get_product(producto()), 1)
        cart.clear()
        assert cart.is_empty


class TestCobro:
    def test_registra_la_venta_y_descuenta_stock(self, app_db):
        product_id = producto("Agua", 1500, stock=10)
        cart = Cart()
        cart.add(products_service.get_product(product_id), 3)

        sale_id = service.checkout(cart)

        venta = service.get_sale(sale_id)
        assert venta.total_cents == 4500
        assert products_service.get_product(product_id).stock == 7

    def test_guarda_el_nombre_y_precio_del_momento(self, app_db):
        """El ticket de hoy no debe cambiar si manana suben el precio."""
        product_id = producto("Agua", 1500, stock=10)
        cart = Cart()
        cart.add(products_service.get_product(product_id), 1)
        sale_id = service.checkout(cart)

        products_service.update_product(
            product_id,
            products_service.ProductForm(name="Agua Premium", price_cents=3000, stock=9),
        )

        linea = service.get_sale(sale_id).lines[0]
        assert linea.product_name == "Agua"
        assert linea.product_price_cents == 1500

    def test_revalida_el_stock_al_cobrar(self, app_db):
        """El carrito guarda el stock que vio; el cobro consulta el real."""
        product_id = producto("Agua", 1500, stock=10)
        cart = Cart()
        cart.add(products_service.get_product(product_id), 8)

        # Alguien ajusta el inventario despues de armar el carrito.
        products_service.adjust_stock(product_id, -5)

        with pytest.raises(InsufficientStockError, match="Quedan 5"):
            service.checkout(cart)

    def test_si_falla_no_deja_la_venta_a_medias(self, app_db):
        bueno = producto("Agua", 1500, stock=10)
        malo = producto("Barra", 2500, stock=10)

        cart = Cart()
        cart.add(products_service.get_product(bueno), 2)
        cart.add(products_service.get_product(malo), 5)

        products_service.adjust_stock(malo, -8)

        with pytest.raises(InsufficientStockError):
            service.checkout(cart)

        _, ventas = service.list_sales(VisitRange.ALL)
        assert ventas == 0
        assert products_service.get_product(bueno).stock == 10

    def test_producto_borrado_entre_carrito_y_cobro(self, app_db):
        product_id = producto("Agua")
        cart = Cart()
        cart.add(products_service.get_product(product_id), 1)
        products_service.delete_product(product_id)

        with pytest.raises(NotFoundError):
            service.checkout(cart)

    def test_carrito_vacio(self, app_db):
        with pytest.raises(ServiceError, match="vacío"):
            service.checkout(Cart())

    def test_totales_del_periodo(self, app_db):
        product_id = producto("Agua", 1500, stock=100)
        for _ in range(3):
            cart = Cart()
            cart.add(products_service.get_product(product_id), 2)
            service.checkout(cart)

        totales = service.totals(VisitRange.TODAY)
        assert totales.count == 3
        assert totales.items == 6
        assert totales.revenue_cents == 9000

    def test_las_ventas_viejas_no_cuentan_hoy(self, app_db):
        product_id = producto("Agua", 1500, stock=100)
        cart = Cart()
        cart.add(products_service.get_product(product_id), 1)
        service.checkout(cart, sold_at=datetime.now() - timedelta(days=40))

        assert service.totals(VisitRange.TODAY).count == 0
        assert service.totals(VisitRange.ALL).count == 1

    def test_productos_mas_vendidos(self, app_db):
        agua = producto("Agua", 1500, stock=100)
        barra = producto("Barra", 2500, stock=100)

        cart = Cart()
        cart.add(products_service.get_product(agua), 5)
        cart.add(products_service.get_product(barra), 1)
        service.checkout(cart)

        top = service.top_products(VisitRange.TODAY)
        assert top[0][0] == "Agua"
        assert top[0][1] == 5


class TestAnulacion:
    def _cobrar(self, product_id: int, quantity: int = 3, sold_at=None) -> int:
        cart = Cart()
        cart.add(products_service.get_product(product_id), quantity)
        return service.checkout(cart, sold_at=sold_at)

    def test_devuelve_el_stock_y_sella_la_venta(self, app_db):
        product_id = producto("Agua", 1500, stock=10)
        sale_id = self._cobrar(product_id, 3)

        service.void_sale(sale_id)

        venta = service.get_sale(sale_id)
        assert venta.is_voided
        assert venta.voided_at is not None
        assert products_service.get_product(product_id).stock == 10

    def test_sigue_en_el_historial(self, app_db):
        product_id = producto("Agua", stock=10)
        self._cobrar(product_id)
        sale_id = self._cobrar(product_id)
        service.void_sale(sale_id)

        filas, total = service.list_sales(VisitRange.TODAY)
        assert total == 2
        assert {venta.id: venta.is_voided for venta in filas}[sale_id]

    def test_el_corte_y_los_totales_la_ignoran(self, app_db):
        product_id = producto("Agua", 1500, stock=10)
        sale_id = self._cobrar(product_id, 2)
        service.void_sale(sale_id)

        totales = service.totals(VisitRange.TODAY)
        assert totales.count == 0
        assert totales.items == 0
        assert totales.revenue_cents == 0
        assert service.top_products(VisitRange.TODAY) == []

    def test_una_venta_cobrada_sigue_contando(self, app_db):
        product_id = producto("Agua", 1500, stock=10)
        self._cobrar(product_id, 2)
        sale_id = self._cobrar(product_id, 1)
        service.void_sale(sale_id)

        totales = service.totals(VisitRange.TODAY)
        assert totales.count == 1
        assert totales.revenue_cents == 3000
        assert totales.items == 2

    def test_rechaza_anular_dos_veces(self, app_db):
        product_id = producto("Agua", stock=10)
        sale_id = self._cobrar(product_id)
        service.void_sale(sale_id)

        with pytest.raises(ServiceError, match="ya está anulada"):
            service.void_sale(sale_id)
        assert products_service.get_product(product_id).stock == 10

    def test_rechaza_ventas_de_otro_dia(self, app_db):
        product_id = producto("Agua", stock=10)
        sale_id = self._cobrar(product_id, sold_at=datetime.now() - timedelta(days=1))

        with pytest.raises(ServiceError, match="ventas de hoy"):
            service.void_sale(sale_id)
        assert products_service.get_product(product_id).stock == 7

    def test_producto_desactivado_igual_recupera_stock(self, app_db):
        product_id = producto("Agua", stock=10)
        sale_id = self._cobrar(product_id, 4)
        products_service.set_active(product_id, False)

        service.void_sale(sale_id)

        assert products_service.get_product(product_id).stock == 10

    def test_venta_inexistente(self, app_db):
        with pytest.raises(NotFoundError):
            service.void_sale(999)


class TestPantallaProductos:
    def test_lista_los_productos(self, qtbot, window):
        producto("Agua")
        producto("Barra")

        page = ProductsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.table.model.rowCount() == 2
        assert page.stat_total.value_label.text() == "2"

    def test_cuenta_stock_bajo_y_agotados(self, qtbot, window):
        producto("Agua", stock=5)
        producto("Toalla", stock=0)
        producto("Cafe", stock=3)
        producto("Electrolit", stock=40)

        page = ProductsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        assert page.stat_total.value_label.text() == "4"
        assert page.stat_low_stock.value_label.text() == "2"
        assert page.stat_out_of_stock.value_label.text() == "1"

    def test_filtra_agotados_en_la_tabla(self, qtbot, window):
        producto("Agua", stock=5)
        producto("Toalla", stock=0)

        page = ProductsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter("out_of_stock")

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Toalla"

    def test_filtra_stock_bajo_en_la_tabla(self, qtbot, window):
        producto("Agua", stock=5)
        producto("Toalla", stock=0)
        producto("Electrolit", stock=40)

        page = ProductsPage(window)
        qtbot.addWidget(page)
        page.refresh()
        page._on_filter("low_stock")

        assert page.table.model.rowCount() == 1
        assert page.table.model.record_at(0).name == "Agua"

    def test_crear_desde_el_dialogo(self, qtbot, window):
        dialog = ProductDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Agua")
        dialog.price_input.setText("15")
        dialog.stock_input.setValue(20)
        dialog.accept()

        rows, _ = products_service.list_products()
        assert rows[0].name == "Agua" and rows[0].stock == 20

    def test_precio_invalido_muestra_error(self, qtbot, window):
        dialog = ProductDialog(window)
        qtbot.addWidget(dialog)
        dialog.name_input.setText("Agua")
        dialog.price_input.setText("abc")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.price_field.error.isVisibleTo(dialog)

    def test_nombre_vacio_muestra_error(self, qtbot, window):
        dialog = ProductDialog(window)
        qtbot.addWidget(dialog)
        dialog.price_input.setText("15")
        dialog.accept()

        assert dialog.result() == 0
        assert dialog.name_field.error.isVisibleTo(dialog)

    def test_sin_seleccion_no_falla(self, qtbot, window):
        page = ProductsPage(window)
        qtbot.addWidget(page)
        page.refresh()

        page.edit_selected()
        page.delete_selected()
        page.toggle_selected()


class TestPantallaPuntoDeVenta:
    def _page(self, qtbot, window):
        page = SalesPage(window)
        qtbot.addWidget(page)
        page.refresh()
        return page

    def test_muestra_el_catalogo_vendible(self, qtbot, window):
        producto("Disponible", stock=5)
        producto("Agotado", stock=0)

        page = self._page(qtbot, window)
        assert page.catalog_table.model.rowCount() == 1

    def test_agregar_al_carrito_actualiza_el_total(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=10)
        page = self._page(qtbot, window)
        page.add_to_cart(products_service.get_product(product_id), 2)

        assert page.cart.item_count == 2
        assert page.total_label.text() == "$30.00"
        assert page.checkout_button.isEnabled()

    def test_no_deja_pasar_del_stock(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=2)
        page = self._page(qtbot, window)
        page.add_to_cart(products_service.get_product(product_id), 5)

        assert page.cart.is_empty

    def test_cobrar_vacia_el_carrito_y_refresca(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.pages.sales.confirm", lambda *a, **k: True)

        product_id = producto("Agua", 1500, stock=10)
        page = self._page(qtbot, window)
        page.add_to_cart(products_service.get_product(product_id), 2)
        page.checkout()

        assert page.cart.is_empty
        assert not page.checkout_button.isEnabled()
        _, total = service.list_sales(VisitRange.TODAY)
        assert total == 1
        assert products_service.get_product(product_id).stock == 8

    def test_cobrar_con_stock_agotado_avisa(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.pages.sales.confirm", lambda *a, **k: True)

        product_id = producto("Agua", 1500, stock=10)
        page = self._page(qtbot, window)
        page.add_to_cart(products_service.get_product(product_id), 8)
        products_service.adjust_stock(product_id, -9)

        page.checkout()

        assert not page.cart.is_empty
        _, total = service.list_sales(VisitRange.ALL)
        assert total == 0

    def test_quitar_una_linea(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=10)
        page = self._page(qtbot, window)
        page.add_to_cart(products_service.get_product(product_id), 2)

        page.cart.remove(product_id)
        page.render_cart()

        assert page.cart.is_empty
        assert page.total_label.text() == "$0.00"

    def test_sin_seleccion_no_falla(self, qtbot, window):
        page = self._page(qtbot, window)
        page.add_selected()
        page.remove_from_cart()


class TestPantallaHistorial:
    def _page(self, qtbot, window):
        page = SalesHistoryPage(window)
        qtbot.addWidget(page)
        page.refresh()
        return page

    def _venta(self, product_id: int, quantity: int = 2, sold_at=None) -> None:
        cart = Cart()
        cart.add(products_service.get_product(product_id), quantity)
        service.checkout(cart, sold_at=sold_at)

    def test_cuenta_ventas_por_periodo(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=100)
        self._venta(product_id)
        self._venta(product_id, sold_at=datetime.now() - timedelta(days=40))

        page = self._page(qtbot, window)
        assert page.stat_today.value_label.text() == "1"
        assert page.stat_week.value_label.text() == "1"
        assert page.stat_month.value_label.text() == "1"
        assert page.stat_all.value_label.text() == "2"
        assert page.table.model.rowCount() == 1

    def test_filtra_por_todas(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=100)
        self._venta(product_id)
        self._venta(product_id, sold_at=datetime.now() - timedelta(days=40))

        page = self._page(qtbot, window)
        page._on_range(VisitRange.ALL)

        assert page.table.model.rowCount() == 2
        assert page.stat_today.value_label.text() == "1"

    def test_ver_detalle_abre_el_ticket(self, qtbot, window):
        product_id = producto("Agua", 1500, stock=10)
        self._venta(product_id, quantity=2)

        page = self._page(qtbot, window)
        page.table.view.selectRow(0)
        sale = page.table.selected_record()
        assert sale is not None

        dialog = SaleDetailDialog(sale.id, page)
        qtbot.addWidget(dialog)
        assert dialog.table.model.rowCount() == 1
        assert (
            dialog.table.model.data(dialog.table.model.index(0, 0), Qt.ItemDataRole.DisplayRole)
            == "Agua"
        )

    def test_sin_seleccion_no_falla(self, qtbot, window):
        page = self._page(qtbot, window)
        page.open_detail()
        page.void_selected()

    def test_anular_devuelve_stock_y_marca_la_fila(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.pages.sale_history.confirm_void", lambda *a, **k: True)

        product_id = producto("Agua", 1500, stock=10)
        self._venta(product_id, quantity=2)

        page = self._page(qtbot, window)
        page.table.view.selectRow(0)
        page.void_selected()

        assert products_service.get_product(product_id).stock == 10
        assert page.stat_today.value_label.text() == "0"
        assert page.table.model.rowCount() == 1
        estado = page.table.model.data(page.table.model.index(0, 3), Qt.ItemDataRole.DisplayRole)
        assert estado == "Anulado"

    def test_anular_desde_el_detalle(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.dialogs.sale_detail.confirm_void", lambda *a, **k: True)

        product_id = producto("Agua", 1500, stock=10)
        self._venta(product_id, quantity=2)

        page = self._page(qtbot, window)
        sale = page.table.model.record_at(0)
        assert sale is not None

        dialog = SaleDetailDialog(sale.id, page)
        qtbot.addWidget(dialog)
        dialog._void(sale)

        assert dialog.voided
        assert products_service.get_product(product_id).stock == 10

    def test_no_anula_ventas_viejas(self, qtbot, window, monkeypatch):
        monkeypatch.setattr("gym.ui.pages.sale_history.confirm_void", lambda *a, **k: True)

        product_id = producto("Agua", 1500, stock=10)
        self._venta(product_id, sold_at=datetime.now() - timedelta(days=1))

        page = self._page(qtbot, window)
        page._on_range(VisitRange.ALL)
        page.table.view.selectRow(0)
        page.void_selected()

        assert not service.get_sale(page.table.selected_record().id).is_voided
        assert products_service.get_product(product_id).stock == 8
