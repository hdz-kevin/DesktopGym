"""Plan, fecha de inicio y vista previa de vigencia.

Lo usan el alta de un socio y la renovacion posterior, para no duplicar el combo,
el calendario y el texto de vigencia.
"""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Plan
from gym.domain.dates import format_date
from gym.domain.money import format_money
from gym.domain.rules import period_end_date
from gym.services import plans as plans_service
from gym.ui.widgets.common import Card
from gym.ui.widgets.inputs import Field


class PlanChargeFields(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        category_id: int | None = None,
        suggested_start: date | None = None,
        selected_plan_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._suggested_start = suggested_start or date.today()
        self._plans: dict[int, Plan] = {}

        self.plan_input = QComboBox(self)
        self.plan_input.currentIndexChanged.connect(self._update_preview)
        self.plan_field = Field("Plan", self.plan_input, self)

        self.start_input = QDateEdit(self)
        self.start_input.setCalendarPopup(True)
        self.start_input.setDisplayFormat("dd/MM/yyyy")
        self.start_input.setEnabled(False)
        self.start_input.setDate(
            QDate(
                self._suggested_start.year,
                self._suggested_start.month,
                self._suggested_start.day,
            )
        )
        self.start_input.dateChanged.connect(self._update_preview)

        self.custom_start = QCheckBox("Elegir otra fecha de inicio", self)
        self.custom_start.toggled.connect(self._on_custom_start)

        start_box = QWidget(self)
        start_layout = QVBoxLayout(start_box)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.setSpacing(6)
        start_layout.addWidget(self.custom_start)
        start_layout.addWidget(self.start_input)
        self.start_field = Field("Inicio", start_box, self)

        self.preview = QLabel("", self)
        self.preview.setObjectName("muted")
        self.preview_card = Card(self)
        self.preview_card.body.addWidget(self.preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.plan_field)
        layout.addWidget(self.start_field)
        layout.addWidget(self.preview_card)

        self.set_category(category_id, selected_plan_id)

    def set_category(self, category_id: int | None, selected_plan_id: int | None = None) -> None:
        self.plan_input.blockSignals(True)
        self.plan_input.clear()
        self._plans = {}
        if category_id:
            for plan in plans_service.list_plans(category_id):
                label = f"{plan.name} ({format_money(plan.price_cents)})"
                self.plan_input.addItem(label, plan.id)
                self._plans[plan.id] = plan
            if selected_plan_id is not None:
                index = self.plan_input.findData(selected_plan_id)
                if index >= 0:
                    self.plan_input.setCurrentIndex(index)
        self.plan_input.blockSignals(False)
        self._update_preview()

    def plan_id(self) -> int | None:
        return self.plan_input.currentData()

    def explicit_start(self) -> date | None:
        """Fecha elegida a mano, o None para que el servicio use la sugerida."""
        if not self.custom_start.isChecked():
            return None
        qdate = self.start_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _on_custom_start(self, checked: bool) -> None:
        self.start_input.setEnabled(checked)
        self._update_preview()

    def _start_date(self) -> date:
        chosen = self.explicit_start()
        return chosen if chosen is not None else self._suggested_start

    def _update_preview(self) -> None:
        plan_id = self.plan_id()
        if plan_id is None:
            self.preview.setText("No hay planes en esta categoría. Ve a Planes (F4).")
            return

        plan = self._plans.get(plan_id)
        if plan is None:
            return

        start = self._start_date()
        end = period_end_date(datetime.combine(start, time()), plan.unit, plan.amount)
        self.preview.setText(
            f"Vigencia: {format_date(start)} al {format_date(end)}\n"
            f"Importe: {format_money(plan.price_cents)}"
        )
