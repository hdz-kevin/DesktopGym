"""Historial de tickets de la tienda."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from gym.data.models import Sale
from gym.domain.dates import format_datetime
from gym.domain.money import format_money
from gym.services import sales as service
from gym.services.visits import VisitRange
from gym.ui.dialogs.sale_detail import SaleDetailDialog
from gym.ui.main_window import Page
from gym.ui.widgets.common import (
    ControlsRow,
    FilterChips,
    PageHeader,
    StatCard,
    secondary_button,
)
from gym.ui.widgets.table import Column, PagedTable

RANGES = [
    (r, r.label()) for r in (VisitRange.TODAY, VisitRange.WEEK, VisitRange.MONTH, VisitRange.ALL)
]


class SalesHistoryPage(Page):
    title = "Historial de Ventas"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._range = VisitRange.TODAY

        header = PageHeader("Historial de Ventas", "Consulta el historial de ventas con detalle")

        self.stat_today = StatCard("Hoy")
        self.stat_week = StatCard("Esta semana")
        self.stat_month = StatCard("Este mes")
        self.stat_all = StatCard("Todas")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_today, self.stat_week, self.stat_month, self.stat_all):
            stats.addWidget(card)

        self.chips = FilterChips(RANGES)
        self.chips.changed.connect(self._on_range)

        controls = ControlsRow()
        controls.addWidget(self.chips, 1)
        controls.addWidget(secondary_button("Ver detalle", self.open_detail))

        self.table = PagedTable[Sale](
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
            page_size=25,
            empty_text="No hay ventas en este periodo.",
        )
        self.table.row_activated.connect(lambda s: SaleDetailDialog(s.id, self).exec())
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
        rows, total = service.list_sales(
            self._range, offset=self.table.offset, limit=self.table.page_size
        )
        self.table.set_data(rows, total)

    def load_stats(self) -> None:
        self.stat_today.set_value(str(service.totals(VisitRange.TODAY).count))
        self.stat_week.set_value(str(service.totals(VisitRange.WEEK).count))
        self.stat_month.set_value(str(service.totals(VisitRange.MONTH).count))
        self.stat_all.set_value(str(service.totals(VisitRange.ALL).count))

    def _on_range(self, range_: VisitRange) -> None:
        self._range = VisitRange(range_)
        self.table.reset_page()
        self.load()

    def open_detail(self) -> None:
        sale = self.table.selected_record()
        if sale is None:
            self.window_ref.notify("Selecciona una venta de la tabla primero.")
            return
        SaleDetailDialog(sale.id, self).exec()
