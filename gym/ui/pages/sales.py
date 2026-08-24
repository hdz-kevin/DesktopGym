"""Punto de venta: catalogo a la izquierda, carrito a la derecha."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Product, Sale
from gym.domain.dates import format_datetime
from gym.domain.money import format_money
from gym.services import products as products_service
from gym.services import sales as service
from gym.services.errors import ServiceError
from gym.services.sales import Cart, CartLine
from gym.services.visits import VisitRange
from gym.ui.main_window import Page
from gym.ui.theme import TEXT_MUTED, WARNING
from gym.ui.widgets.common import (
    Card,
    FilterChips,
    PageHeader,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import confirm
from gym.ui.widgets.inputs import SearchBox
from gym.ui.widgets.table import Column, PagedTable

RANGES = [
    (r, r.label()) for r in (VisitRange.TODAY, VisitRange.WEEK, VisitRange.MONTH, VisitRange.ALL)
]


def _stock_text(product: Product) -> str:
    if product.stock is None:
        return "—"
    return str(product.stock)


class SaleDetailDialog(QDialog):
    def __init__(self, sale_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        sale = service.get_sale(sale_id)
        self.setWindowTitle(f"Venta del {format_datetime(sale.sold_at)}")
        self.setModal(True)
        self.setMinimumSize(560, 380)

        table = PagedTable(
            columns=[
                Column("Producto", lambda line: line.product_name, stretch=True),
                Column(
                    "Cantidad",
                    lambda line: line.quantity,
                    width=90,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
                Column(
                    "Precio",
                    lambda line: format_money(line.product_price_cents),
                    width=100,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
                Column(
                    "Subtotal",
                    lambda line: format_money(line.subtotal_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=100,
            empty_text="Esta venta no tiene líneas.",
        )
        table.set_data(list(sale.lines), len(sale.lines))

        total = QLabel(f"Total: {format_money(sale.total_cents)}", self)
        total.setObjectName("statValue")

        footer = QHBoxLayout()
        footer.addWidget(total)
        footer.addStretch(1)
        footer.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(table, 1)
        layout.addLayout(footer)


class SalesPage(Page):
    title = "Ventas"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self.cart = Cart()
        self._range = VisitRange.TODAY
        self._catalog_search = ""

        header = PageHeader("Ventas", "Punto de venta y historial de la tienda")
        header.add_action(secondary_button("Ver detalle", self.open_detail))

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addLayout(self._pos_section(), 3)
        layout.addLayout(self._history_section(), 2)

    # --- Punto de venta ---------------------------------------------------

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
                    color=lambda p: WARNING if p.stock is not None and p.stock <= 5 else None,
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

        catalog = QVBoxLayout()
        catalog.setSpacing(8)
        catalog.addWidget(self.catalog_search)
        catalog.addWidget(self.catalog_table, 1)
        catalog.addLayout(add_row)

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
        section.addLayout(catalog, 3)
        section.addWidget(cart_card, 2)
        return section

    # --- Historial --------------------------------------------------------

    def _history_section(self) -> QVBoxLayout:
        self.range_chips = FilterChips(RANGES)
        self.range_chips.changed.connect(self._on_range)

        self.history_table = PagedTable[Sale](
            columns=[
                Column("Fecha y hora", lambda s: format_datetime(s.sold_at), stretch=True),
                Column(
                    "Artículos",
                    lambda s: sum(line.quantity for line in s.lines),
                    width=100,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
                Column(
                    "Total",
                    lambda s: format_money(s.total_cents),
                    width=120,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=15,
            empty_text="No hay ventas en este periodo.",
        )
        self.history_table.row_activated.connect(lambda s: SaleDetailDialog(s.id, self).exec())
        self.history_table.page_changed.connect(lambda _: self.load_history())

        self.history_summary = QLabel("", self)
        self.history_summary.setStyleSheet(f"color: {TEXT_MUTED};")

        title_row = QHBoxLayout()
        history_title = QLabel("Historial de ventas", self)
        history_title.setObjectName("formLabel")
        title_row.addWidget(history_title)
        title_row.addStretch(1)
        title_row.addWidget(self.history_summary)

        section = QVBoxLayout()
        section.setSpacing(8)
        section.addLayout(title_row)
        section.addWidget(self.range_chips)
        section.addWidget(self.history_table, 1)
        return section

    # --- Acciones ---------------------------------------------------------

    def refresh(self) -> None:
        self.load_catalog()
        self.load_history()
        self.render_cart()

    def load_catalog(self) -> None:
        rows = products_service.sellable_products(self._catalog_search)
        self.catalog_table.set_data(rows, len(rows))

    def load_history(self) -> None:
        rows, total = service.list_sales(
            self._range, offset=self.history_table.offset, limit=self.history_table.page_size
        )
        self.history_table.set_data(rows, total)

        totals = service.totals(self._range)
        self.history_summary.setText(
            f"{totals.count} venta(s) · {totals.items} artículo(s) · "
            f"{format_money(totals.revenue_cents)}"
        )

    def render_cart(self) -> None:
        lines = self.cart.ordered_lines()
        self.cart_table.set_data(lines, len(lines))
        self.total_label.setText(format_money(self.cart.total_cents))
        self.items_label.setText(f"{self.cart.item_count} artículo(s)")
        self.checkout_button.setEnabled(not self.cart.is_empty)

    def _on_catalog_search(self, text: str) -> None:
        self._catalog_search = text
        self.load_catalog()

    def _on_range(self, range_: VisitRange) -> None:
        self._range = VisitRange(range_)
        self.history_table.reset_page()
        self.load_history()

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

    def open_detail(self) -> None:
        sale = self.history_table.selected_record()
        if sale is None:
            self.window_ref.notify("Selecciona una venta del historial primero.")
            return
        SaleDetailDialog(sale.id, self).exec()
