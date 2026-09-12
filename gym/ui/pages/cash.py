"""Corte de caja."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.domain.money import format_money
from gym.services import cash as service
from gym.services import sales as sales_service
from gym.services.cash import CashReport, ConceptTotal
from gym.services.visits import VisitRange
from gym.ui.main_window import Page
from gym.ui.theme import SUCCESS, TEXT_MUTED
from gym.ui.widgets.common import Card, FilterChips, PageHeader, StatCard
from gym.ui.widgets.table import Column, PagedTable

RANGES = [(r, r.label()) for r in (VisitRange.TODAY, VisitRange.WEEK, VisitRange.MONTH)]


class ConceptRow(QWidget):
    """Una linea del desglose: concepto, cantidad e importe."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name_label = QLabel(label, self)
        self.count_label = QLabel("0", self)
        self.count_label.setStyleSheet(f"color: {TEXT_MUTED};")
        self.count_label.setFixedWidth(120)
        self.amount_label = QLabel("$0.00", self)
        self.amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.amount_label.setFixedWidth(120)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.addWidget(self.name_label, 1)
        row.addWidget(self.count_label)
        row.addWidget(self.amount_label)

    def set_values(self, total: ConceptTotal, unit: str) -> None:
        self.count_label.setText(f"{total.count} {unit}")
        self.amount_label.setText(format_money(total.revenue_cents))


class CashPage(Page):
    title = "Corte de caja"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._range = VisitRange.TODAY

        header = PageHeader("Corte de caja", "Ingresos por concepto")

        self.chips = FilterChips(RANGES)
        self.chips.changed.connect(self._on_range)

        self.stat_total = StatCard("Ingresos totales")
        self.stat_total.value_label.setStyleSheet(f"color: {SUCCESS};")
        self.stat_memberships = StatCard("Membresías")
        self.stat_visits = StatCard("Visitas")
        self.stat_store = StatCard("Ventas")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (
            self.stat_total,
            self.stat_memberships,
            self.stat_visits,
            self.stat_store,
        ):
            stats.addWidget(card)

        self.row_new = ConceptRow("Altas nuevas de membresía")
        self.row_renewals = ConceptRow("Renovaciones de membresía")
        self.row_visits = ConceptRow("Visitas")
        self.row_sales = ConceptRow("Ventas de productos")

        self.total_row = ConceptRow("Total")
        self.total_row.name_label.setStyleSheet("font-weight: 700;")
        self.total_row.amount_label.setStyleSheet(f"font-weight: 700; color: {SUCCESS};")

        breakdown = Card(self)
        title = QLabel("Desglose por concepto", breakdown)
        title.setObjectName("formLabel")
        breakdown.body.addWidget(title)
        for row in (self.row_new, self.row_renewals, self.row_visits, self.row_sales):
            breakdown.body.addWidget(row)
        breakdown.body.addWidget(self.total_row)

        self.top_table = PagedTable[tuple](
            columns=[
                Column("Producto", lambda r: r[0], stretch=True),
                Column(
                    "Piezas",
                    lambda r: r[1],
                    width=80,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
                Column(
                    "Importe",
                    lambda r: format_money(r[2]),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=5,
            empty_text="Sin ventas en este periodo.",
        )

        top_card = Card(self)
        top_title = QLabel("Productos más vendidos", top_card)
        top_title.setObjectName("formLabel")
        top_card.body.addWidget(top_title)
        top_card.body.addWidget(self.top_table)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(breakdown, 3)
        columns.addWidget(top_card, 2)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.addWidget(header)
        layout.addWidget(self.chips)
        layout.addLayout(stats)
        layout.addLayout(columns, 1)
        layout.addStretch(1)

    def refresh(self) -> None:
        report = service.build_report(self._range)
        self._render(report)

        top = sales_service.top_products(self._range, limit=5)
        self.top_table.set_data(top, len(top))

    def _render(self, report: CashReport) -> None:
        self.stat_total.set_value(format_money(report.total_revenue_cents))
        self.stat_total.caption.setText(f"Ingresos · {report.range_.label()}")
        self.stat_memberships.set_value(format_money(report.memberships_revenue_cents))
        self.stat_visits.set_value(format_money(report.visits.revenue_cents))
        self.stat_store.set_value(format_money(report.sales.revenue_cents))

        self.row_new.set_values(report.new_memberships, "alta(s)")
        self.row_renewals.set_values(report.renewals, "renovación(es)")
        self.row_visits.set_values(report.visits, "visita(s)")
        self.row_sales.set_values(report.sales, "venta(s)")

        self.total_row.count_label.setText(f"{report.transaction_count} movimiento(s)")
        self.total_row.amount_label.setText(format_money(report.total_revenue_cents))

    def _on_range(self, range_: VisitRange) -> None:
        self._range = VisitRange(range_)
        self.refresh()
