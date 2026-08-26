"""Historial de periodos pagados de una membresia."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.data.models import Period
from gym.domain.dates import format_range
from gym.domain.money import format_money
from gym.services import memberships as service
from gym.services.errors import ServiceError
from gym.ui.dialogs.membership_form import PeriodFormDialog
from gym.ui.theme import DANGER, SUCCESS
from gym.ui.widgets.common import danger_button, secondary_button, status_badge
from gym.ui.widgets.feedback import confirm
from gym.ui.widgets.table import Column, PagedTable

STATUS_COLORS = {"in_progress": SUCCESS, "completed": DANGER}


class MembershipHistoryDialog(QDialog):
    def __init__(self, membership_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.membership_id = membership_id
        self.changed = False

        membership = service.get_membership(membership_id)
        self.setWindowTitle(f"Historial · {membership.member.name}")
        self.setModal(True)
        self.setMinimumSize(720, 460)

        self.summary = QLabel("", self)
        self.summary.setObjectName("muted")

        self.table = PagedTable[Period](
            columns=[
                Column("Periodo", lambda p: format_range(p.start_date, p.end_date), stretch=True),
                Column("Plan", lambda p: p.plan.name, width=130),
                Column(
                    "Importe",
                    lambda p: format_money(p.price_paid_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
                Column(
                    "Estado",
                    lambda p: p.status.label(),
                    width=120,
                    color=lambda p: STATUS_COLORS.get(p.status.value),
                ),
            ],
            page_size=50,
            empty_text="Esta membresía no tiene periodos.",
        )
        self.table.row_activated.connect(lambda _: self.edit_selected())

        buttons = QHBoxLayout()
        buttons.addWidget(secondary_button("Editar periodo", self.edit_selected))
        buttons.addWidget(danger_button("Eliminar periodo", self.delete_selected))
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self._heading(membership))
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

        self.load()

    def _heading(self, membership) -> QWidget:
        box = QWidget(self)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel(membership.plan_category.name, box)
        title.setObjectName("pageTitle")
        row.addWidget(title)
        row.addWidget(status_badge(membership.status))
        row.addStretch(1)
        return box

    def load(self) -> None:
        membership = service.get_membership(self.membership_id)
        periods = sorted(membership.periods, key=lambda p: p.start_date, reverse=True)
        self.table.set_data(periods, len(periods))
        self.summary.setText(
            f"{len(periods)} periodo(s) · Total pagado: {format_money(membership.total_paid_cents)}"
        )

    def edit_selected(self) -> None:
        period = self.table.selected_record()
        if period is None:
            return
        if PeriodFormDialog(period, self).exec():
            self.changed = True
            self.load()

    def delete_selected(self) -> None:
        period = self.table.selected_record()
        if period is None:
            return

        if not confirm(
            self,
            "Eliminar periodo",
            f"¿Eliminar el periodo {format_range(period.start_date, period.end_date)}?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_period(period.id)
        except ServiceError as error:
            from gym.ui.widgets.feedback import alert

            alert(self, "No se puede eliminar", str(error))
            return

        self.changed = True
        self.load()
