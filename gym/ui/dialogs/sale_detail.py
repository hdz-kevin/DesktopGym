"""Detalle de un ticket de tienda. Solo lectura: las ventas no se corrigen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.domain.dates import format_datetime
from gym.domain.money import format_money
from gym.services import sales as service
from gym.ui.widgets.common import secondary_button
from gym.ui.widgets.table import Column, PagedTable


class SaleDetailDialog(QDialog):
    def __init__(self, sale_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        sale = service.get_sale(sale_id)
        self.setWindowTitle(f"Venta del {format_datetime(sale.sold_at)}")
        self.setModal(True)
        self.setMinimumSize(740, 450)

        self.table = PagedTable(
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
        self.table.set_data(list(sale.lines), len(sale.lines))

        total = QLabel(f"Total: {format_money(sale.total_cents)}", self)
        total.setObjectName("statValue")

        footer = QHBoxLayout()
        footer.addWidget(total)
        footer.addStretch(1)
        footer.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.table, 1)
        layout.addLayout(footer)
