"""Detalle de un ticket de tienda. Solo lectura: las ventas no se corrigen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Sale
from gym.domain.dates import format_datetime
from gym.domain.money import format_money
from gym.services import sales as service
from gym.ui.widgets.common import secondary_button
from gym.ui.widgets.table import Column, PagedTable


class SaleDetailDialog(QDialog):
    def __init__(self, sale_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("saleDetail")
        sale = service.get_sale(sale_id)
        self.setWindowTitle("Detalle de venta")
        self.setModal(True)
        self.setMinimumSize(760, 500)

        details = QFormLayout()
        details.setVerticalSpacing(14)
        details.setHorizontalSpacing(16)
        details.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        details.addRow(self._label("Artículos"), QLabel(str(sale.item_count), self))
        details.addRow(self._label("Total"), QLabel(format_money(sale.total_cents), self))

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

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(20)
        body.addWidget(self._heading(sale))
        body.addLayout(details)
        body.addWidget(self.table, 1)

        layout.addLayout(body, 1)
        layout.addLayout(buttons)

    def _heading(self, sale: Sale) -> QWidget:
        box = QWidget(self)
        box.setObjectName("saleHeading")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel(f"Venta del {format_datetime(sale.sold_at)}", box)
        title.setObjectName("pageTitle")
        row.addWidget(title)
        row.addStretch(1)
        return box

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label
