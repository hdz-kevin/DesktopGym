"""Punto de venta: catalogo a la izquierda, carrito a la derecha."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QVBoxLayout

from gym.data.models import Product
from gym.domain.money import format_money
from gym.services import products as products_service
from gym.services import sales as service
from gym.services.errors import ServiceError
from gym.services.sales import Cart, CartLine
from gym.ui.main_window import Page
from gym.ui.theme import TEXT_MUTED, WARNING
from gym.ui.widgets.common import Card, PageHeader, danger_button, primary_button, secondary_button
from gym.ui.widgets.feedback import confirm
from gym.ui.widgets.inputs import SearchBox
from gym.ui.widgets.table import Column, PagedTable


def _stock_text(product: Product) -> str:
    return str(product.stock)


class SalesPage(Page):
    title = "Punto de venta"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self.cart = Cart()
        self._catalog_search = ""

        header = PageHeader("Punto de venta", "Registro y cobro de ventas de productos")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.addWidget(header)
        layout.addLayout(self._pos_section(), 3)
        layout.addStretch(1)

    def _pos_section(self) -> QHBoxLayout:
        self.catalog_search = SearchBox("Buscar producto para agregar...")
        self.catalog_search.search_changed.connect(self._on_catalog_search)

        self.catalog_table = PagedTable[Product](
            columns=[
                Column("Producto", lambda p: p.name, stretch=True),
                Column(
                    "Precio",
                    lambda p: format_money(p.price_cents),
                    width=100,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
                Column(
                    "Stock",
                    _stock_text,
                    width=70,
                    align=Qt.AlignmentFlag.AlignCenter,
                    color=lambda p: WARNING if p.stock <= 5 else None,
                ),
            ],
            page_size=100,
            empty_text="No hay productos disponibles. Revisa el catálogo en Productos (F7).",
        )
        self.catalog_table.row_activated.connect(self.add_to_cart)

        self.quantity_input = QSpinBox(self)
        self.quantity_input.setRange(1, 999)
        self.quantity_input.setValue(1)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        add_row.addWidget(QLabel("Cantidad:", self))
        add_row.addWidget(self.quantity_input)
        add_row.addWidget(primary_button("Agregar al carrito", self.add_selected))
        add_row.addStretch(1)

        catalog_card = Card(self)
        catalog_title = QLabel("Productos", catalog_card)
        catalog_title.setObjectName("formLabel")
        catalog_card.body.addWidget(catalog_title)
        catalog_card.body.addWidget(self.catalog_search)
        catalog_card.body.addWidget(self.catalog_table, 1)
        catalog_card.body.addLayout(add_row)

        self.cart_table = PagedTable[CartLine](
            columns=[
                Column("Producto", lambda line: line.name, stretch=True),
                Column(
                    "Cant.",
                    lambda line: line.quantity,
                    width=60,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
                Column(
                    "Subtotal",
                    lambda line: format_money(line.subtotal_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=100,
            empty_text="El carrito está vacío.",
            paginated=False,
        )

        self.total_label = QLabel("$0.00", self)
        self.total_label.setObjectName("statValue")
        self.items_label = QLabel("0 artículos", self)
        self.items_label.setStyleSheet(f"color: {TEXT_MUTED};")

        self.checkout_button = primary_button("Cobrar", self.checkout)
        self.checkout_button.setEnabled(False)

        cart_buttons = QHBoxLayout()
        cart_buttons.setSpacing(8)
        cart_buttons.addWidget(secondary_button("Quitar", self.remove_from_cart))
        cart_buttons.addWidget(danger_button("Vaciar", self.clear_cart))
        cart_buttons.addStretch(1)
        cart_buttons.addWidget(self.checkout_button)

        cart_card = Card(self)
        cart_title = QLabel("Carrito", cart_card)
        cart_title.setObjectName("formLabel")
        cart_card.body.addWidget(cart_title)
        cart_card.body.addWidget(self.cart_table, 1)
        cart_card.body.addWidget(self.items_label)
        cart_card.body.addWidget(self.total_label)
        cart_card.body.addLayout(cart_buttons)

        section = QHBoxLayout()
        section.setSpacing(16)
        section.addWidget(catalog_card, 3)
        section.addWidget(cart_card, 2)
        return section

    def refresh(self) -> None:
        self.load_catalog()
        self.render_cart()

    def load_catalog(self) -> None:
        rows = products_service.sellable_products(self._catalog_search)
        self.catalog_table.set_data(rows, len(rows))

    def render_cart(self) -> None:
        lines = self.cart.ordered_lines()
        self.cart_table.set_data(lines, len(lines))
        self.total_label.setText(format_money(self.cart.total_cents))
        self.items_label.setText(f"{self.cart.item_count} artículo(s)")
        self.checkout_button.setEnabled(not self.cart.is_empty)

    def _on_catalog_search(self, text: str) -> None:
        self._catalog_search = text
        self.load_catalog()

    def add_selected(self) -> None:
        product = self.catalog_table.selected_record()
        if product is None:
            self.window_ref.notify("Selecciona un producto del catálogo primero.")
            return
        self.add_to_cart(product, self.quantity_input.value())

    def add_to_cart(self, product: Product, quantity: int = 1) -> None:
        try:
            self.cart.add(product, quantity)
        except ServiceError as error:
            self.window_ref.notify_error(str(error))
            return

        self.quantity_input.setValue(1)
        self.render_cart()

    def remove_from_cart(self) -> None:
        line = self.cart_table.selected_record()
        if line is None:
            self.window_ref.notify("Selecciona una línea del carrito primero.")
            return
        self.cart.remove(line.product_id)
        self.render_cart()

    def clear_cart(self) -> None:
        if self.cart.is_empty:
            return
        if confirm(self, "Vaciar carrito", "¿Quitar todos los artículos del carrito?"):
            self.cart.clear()
            self.render_cart()

    def checkout(self) -> None:
        if self.cart.is_empty:
            return

        if not confirm(
            self,
            "Cobrar venta",
            f"Total a cobrar: {format_money(self.cart.total_cents)}\n"
            f"{self.cart.item_count} artículo(s).",
            confirm_text="Cobrar",
        ):
            return

        try:
            service.checkout(self.cart)
        except ServiceError as error:
            # El stock pudo cambiar entre armar el carrito y cobrar.
            self.window_ref.notify_error(str(error))
            self.load_catalog()
            return

        self.cart.clear()
        self.window_ref.notify_success("Venta registrada.")
        self.refresh()
