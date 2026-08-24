"""Pantalla de visitas sueltas."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Visit
from gym.domain.dates import format_datetime
from gym.domain.money import format_money
from gym.services import visits as service
from gym.services.errors import ServiceError
from gym.services.visits import VisitRange
from gym.ui.main_window import Page
from gym.ui.widgets.common import (
    FilterChips,
    PageHeader,
    StatCard,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import confirm
from gym.ui.widgets.inputs import Field, MoneyInput
from gym.ui.widgets.table import Column, PagedTable

FILTERS = [
    (r, r.label()) for r in (VisitRange.TODAY, VisitRange.WEEK, VisitRange.MONTH, VisitRange.ALL)
]


class VisitDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        visit: Visit | None = None,
        default_price_cents: int = 4000,
    ) -> None:
        super().__init__(parent)
        self.visit = visit
        self.setWindowTitle("Editar visita" if visit else "Registrar visita")
        self.setModal(True)
        self.setMinimumWidth(400)

        self.price_input = MoneyInput(self)
        self.price_input.set_cents(visit.price_cents if visit else default_price_cents)
        self.price_field = Field("Importe cobrado", self.price_input, self)

        moment = visit.visit_at if visit else datetime.now()
        self.date_input = QDateEdit(self)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setDate(QDate(moment.year, moment.month, moment.day))

        self.time_input = QTimeEdit(self)
        self.time_input.setDisplayFormat("hh:mm")
        self.time_input.setTime(QTime(moment.hour, moment.minute))

        when_box = QWidget(self)
        when_row = QHBoxLayout(when_box)
        when_row.setContentsMargins(0, 0, 0, 0)
        when_row.setSpacing(8)
        when_row.addWidget(self.date_input, 2)
        when_row.addWidget(self.time_input, 1)
        self.when_field = Field("Fecha y hora", when_box, self)

        save = primary_button("Guardar", self.accept)
        save.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.price_field)
        layout.addWidget(self.when_field)
        layout.addLayout(buttons)

        self.price_input.setFocus()
        self.price_input.selectAll()

    def _moment(self) -> datetime:
        qdate = self.date_input.date()
        qtime = self.time_input.time()
        return datetime.combine(
            date(qdate.year(), qdate.month(), qdate.day()),
            time(qtime.hour(), qtime.minute()),
        )

    def accept(self) -> None:
        self.price_field.clear_error()
        if not self.price_input.is_valid():
            self.price_field.show_error("Escribe un importe válido, por ejemplo 40.00")
            return

        try:
            if self.visit is None:
                service.create_visit(self.price_input.cents(), self._moment())
            else:
                service.update_visit(self.visit.id, self.price_input.cents(), self._moment())
        except ServiceError as error:
            self.price_field.show_error(str(error))
            return
        super().accept()


class VisitsPage(Page):
    title = "Visitas"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._range = VisitRange.TODAY

        header = PageHeader("Visitas", "Entradas sueltas de quienes no son socios")
        header.add_action(secondary_button("Editar", self.edit_selected))
        header.add_action(danger_button("Eliminar", self.delete_selected))
        header.add_action(primary_button("Registrar visita", self.create_visit))

        self.stat_count = StatCard("Visitas en el periodo")
        self.stat_revenue = StatCard("Ingresos del periodo")
        self.stat_today = StatCard("Visitas de hoy")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_count, self.stat_revenue, self.stat_today):
            stats.addWidget(card)

        self.chips = FilterChips(FILTERS)
        self.chips.changed.connect(self._on_range)

        self.table = PagedTable[Visit](
            columns=[
                Column("Fecha y hora", lambda v: format_datetime(v.visit_at), stretch=True),
                Column(
                    "Importe",
                    lambda v: format_money(v.price_cents),
                    width=120,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=25,
            empty_text="No hay visitas registradas en este periodo.",
        )
        self.table.row_activated.connect(lambda _: self.edit_selected())
        self.table.page_changed.connect(lambda _: self.load())

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addLayout(stats)
        layout.addWidget(self.chips)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.load()
        self.load_stats()

    def load(self) -> None:
        rows, total = service.list_visits(
            self._range, offset=self.table.offset, limit=self.table.page_size
        )
        self.table.set_data(rows, total)

    def load_stats(self) -> None:
        period = service.totals(self._range)
        today = service.totals(VisitRange.TODAY)

        self.stat_count.set_value(str(period.count))
        self.stat_count.caption.setText(f"Visitas · {self._range.label()}")
        self.stat_revenue.set_value(format_money(period.revenue_cents))
        self.stat_revenue.caption.setText(f"Ingresos · {self._range.label()}")
        self.stat_today.set_value(str(today.count))

    def _on_range(self, range_: VisitRange) -> None:
        self._range = VisitRange(range_)
        self.table.reset_page()
        self.refresh()

    def create_visit(self) -> None:
        dialog = VisitDialog(self, default_price_cents=self.window_ref.settings.visit_price_cents)
        if dialog.exec():
            self.window_ref.notify_success("Visita registrada.")
            self.refresh()

    def edit_selected(self) -> None:
        visit = self._require_selection()
        if visit is None:
            return
        if VisitDialog(self, visit).exec():
            self.window_ref.notify_success("Visita actualizada.")
            self.refresh()

    def delete_selected(self) -> None:
        visit = self._require_selection()
        if visit is None:
            return

        if not confirm(
            self,
            "Eliminar visita",
            f"¿Eliminar la visita de {format_datetime(visit.visit_at)} "
            f"por {format_money(visit.price_cents)}?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_visit(visit.id)
        except ServiceError as error:
            self.window_ref.notify_error(str(error))
            return

        self.window_ref.notify_success("Visita eliminada.")
        self.refresh()

    def _require_selection(self) -> Visit | None:
        visit = self.table.selected_record()
        if visit is None:
            self.window_ref.notify("Selecciona una visita de la tabla primero.")
        return visit
