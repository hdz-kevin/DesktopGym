"""Catalogo de productos de la tienda."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Product
from gym.domain.money import format_money
from gym.services import products as service
from gym.services.errors import ServiceError, ValidationError
from gym.ui.main_window import Page
from gym.ui.theme import DANGER, TEXT_MUTED, WARNING
from gym.ui.widgets.common import (
    FilterChips,
    PageHeader,
    StatCard,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import alert, confirm
from gym.ui.widgets.inputs import Field, MoneyInput, SearchBox
from gym.ui.widgets.table import Column, PagedTable

LOW_STOCK_THRESHOLD = service.LOW_STOCK_THRESHOLD


def _stock_text(product: Product) -> str:
    if product.stock == 0:
        return "Agotado"
    return str(product.stock)


def _stock_color(product: Product) -> str | None:
    if product.stock == 0:
        return DANGER
    if product.stock <= LOW_STOCK_THRESHOLD:
        return WARNING
    return None


class ProductDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, product: Product | None = None) -> None:
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Editar producto" if product else "Nuevo producto")
        self.setModal(True)
        self.setMinimumWidth(420)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Por ejemplo: Agua 600 ml")
        self.name_field = Field("Nombre", self.name_input, self)

        self.price_input = MoneyInput(self)
        self.price_field = Field("Precio", self.price_input, self)

        self.stock_input = QSpinBox(self)
        self.stock_input.setRange(0, 999_999)
        self.stock_field = Field("Existencias", self.stock_input, self)

        self.active_input = QCheckBox("Disponible para venta", self)
        self.active_input.setChecked(True)

        if product is not None:
            self._load(product)

        save = primary_button("Guardar", self.accept)
        save.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.name_field)
        layout.addWidget(self.price_field)
        layout.addWidget(self.stock_field)
        layout.addWidget(self.active_input)
        layout.addLayout(buttons)

        self.name_input.setFocus()

    def _load(self, product: Product) -> None:
        self.name_input.setText(product.name)
        self.price_input.set_cents(product.price_cents)
        self.stock_input.setValue(product.stock)
        self.active_input.setChecked(product.is_active)

    def build_form(self) -> service.ProductForm:
        return service.ProductForm(
            name=self.name_input.text(),
            price_cents=self.price_input.cents() if self.price_input.is_valid() else -1,
            stock=self.stock_input.value(),
            is_active=self.active_input.isChecked(),
        )

    def accept(self) -> None:
        for field in (self.name_field, self.price_field, self.stock_field):
            field.clear_error()

        if not self.price_input.is_valid():
            self.price_field.show_error("Escribe un precio válido, por ejemplo 25.00")
            return

        form = self.build_form()
        try:
            if self.product is None:
                service.create_product(form)
            else:
                service.update_product(self.product.id, form)
        except ValidationError as error:
            mapping = {
                "name": self.name_field,
                "price": self.price_field,
                "stock": self.stock_field,
            }
            for key, message in error.errors.items():
                field = mapping.get(key)
                if field:
                    field.show_error(message)
            return
        except ServiceError as error:
            self.name_field.show_error(str(error))
            return
        super().accept()


class ProductsPage(Page):
    title = "Productos"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._search = ""
        self._stock = None

        header = PageHeader("Productos", "Catálogo e inventario de la tienda")

        self.stat_total = StatCard("Productos")
        self.stat_low_stock = StatCard("Stock bajo")
        self.stat_out_of_stock = StatCard("Agotados")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_total, self.stat_low_stock, self.stat_out_of_stock):
            stats.addWidget(card)

        self.search_box = SearchBox("Buscar producto...")
        self.search_box.setFixedWidth(320)
        self.search_box.search_changed.connect(self._on_search)

        self.chips = FilterChips(
            [(None, "Todos"), ("low_stock", "Stock bajo"), ("out_of_stock", "Agotados")]
        )
        self.chips.changed.connect(self._on_filter)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.addWidget(self.search_box)
        controls.addWidget(self.chips, 1)
        controls.addWidget(secondary_button("Editar", self.edit_selected))
        controls.addWidget(secondary_button("Activar/Desactivar", self.toggle_selected))
        controls.addWidget(danger_button("Eliminar", self.delete_selected))
        controls.addWidget(primary_button("Nuevo producto", self.create_product))

        self.table = PagedTable[Product](
            columns=[
                Column("Producto", lambda p: p.name, stretch=True),
                Column(
                    "Precio",
                    lambda p: format_money(p.price_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
                Column(
                    "Stock",
                    _stock_text,
                    width=120,
                    align=Qt.AlignmentFlag.AlignCenter,
                    color=_stock_color,
                ),
                Column(
                    "Estado",
                    lambda p: "Activo" if p.is_active else "Inactivo",
                    width=120,
                    color=lambda p: None if p.is_active else TEXT_MUTED,
                ),
            ],
            page_size=25,
            empty_text="No hay productos en el catálogo.",
        )
        self.table.row_activated.connect(lambda _: self.edit_selected())
        self.table.page_changed.connect(lambda _: self.load())

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.addWidget(header)
        layout.addLayout(stats)
        layout.addLayout(controls)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.load()
        self.load_stats()

    def load(self) -> None:
        rows, total = service.list_products(
            search=self._search,
            stock=self._stock,
            offset=self.table.offset,
            limit=self.table.page_size,
        )
        self.table.set_data(rows, total)

    def load_stats(self) -> None:
        _, total = service.list_products()
        _, low_stock = service.list_products(stock="low_stock")
        _, out_of_stock = service.list_products(stock="out_of_stock")
        self.stat_total.set_value(str(total))
        self.stat_low_stock.set_value(str(low_stock))
        self.stat_out_of_stock.set_value(str(out_of_stock))

    def _on_search(self, text: str) -> None:
        self._search = text
        self.table.reset_page()
        self.load()

    def _on_filter(self, stock: str | None) -> None:
        self._stock = stock
        self.table.reset_page()
        self.load()

    def create_product(self) -> None:
        if ProductDialog(self).exec():
            self.window_ref.notify_success("Producto creado.")
            self.refresh()

    def edit_selected(self) -> None:
        product = self._require_selection()
        if product is None:
            return
        if ProductDialog(self, product).exec():
            self.window_ref.notify_success("Producto actualizado.")
            self.refresh()

    def toggle_selected(self) -> None:
        product = self._require_selection()
        if product is None:
            return

        try:
            service.set_active(product.id, not product.is_active)
        except ServiceError as error:
            self.window_ref.notify_error(str(error))
            return

        estado = "desactivado" if product.is_active else "activado"
        self.window_ref.notify_success(f"Producto {estado}.")
        self.refresh()

    def delete_selected(self) -> None:
        product = self._require_selection()
        if product is None:
            return

        if not confirm(
            self,
            "Eliminar producto",
            f"¿Eliminar «{product.name}» del catálogo?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_product(product.id)
        except ServiceError as error:
            alert(self, "No se puede eliminar", str(error))
            return

        self.window_ref.notify_success("Producto eliminado.")
        self.refresh()

    def _require_selection(self) -> Product | None:
        product = self.table.selected_record()
        if product is None:
            self.window_ref.notify("Selecciona un producto de la tabla primero.")
        return product
