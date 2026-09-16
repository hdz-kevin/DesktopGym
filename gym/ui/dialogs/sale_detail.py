"""Detalle de un ticket de tienda. Se puede anular, no editar."""

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
from gym.services.errors import ServiceError
from gym.ui.widgets.common import Badge, danger_button, secondary_button
from gym.ui.widgets.feedback import alert, confirm
from gym.ui.widgets.table import Column, PagedTable


def confirm_void(parent: QWidget, sale: Sale) -> bool:
    return confirm(
        parent,
        "Anular venta",
        f"Se devolverán {sale.item_count} pieza(s) al inventario y el corte "
        f"de hoy dejará de contar {format_money(sale.total_cents)}.\n\n"
        "Esta acción no se puede deshacer.",
        confirm_text="Anular",
        destructive=True,
    )


class SaleDetailDialog(QDialog):
    def __init__(self, sale_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("saleDetail")
        self.sale_id = sale_id
        self.voided = False
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
        if sale.is_voided and sale.voided_at is not None:
            details.addRow(self._label("Anulada"), QLabel(format_datetime(sale.voided_at), self))

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
        if service.can_void(sale):
            buttons.addWidget(danger_button("Anular", lambda: self._void(sale)))
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

    def _void(self, sale: Sale) -> None:
        if not confirm_void(self, sale):
            return
        try:
            service.void_sale(self.sale_id)
        except ServiceError as error:
            alert(self, "No se puede anular", str(error))
            return
        self.voided = True
        self.accept()

    def _heading(self, sale: Sale) -> QWidget:
        box = QWidget(self)
        box.setObjectName("saleHeading")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel(f"Venta del {format_datetime(sale.sold_at)}", box)
        title.setObjectName("pageTitle")
        row.addWidget(title)
        if sale.is_voided:
            row.addWidget(Badge("Anulado", "badgeNeutral", box))
        else:
            row.addWidget(Badge("Cobrado", "badgeSuccess", box))
        row.addStretch(1)
        return box

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label
