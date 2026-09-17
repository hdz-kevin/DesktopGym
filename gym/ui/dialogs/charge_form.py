"""Cobro de un plan al socio."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Member
from gym.domain.dates import format_date
from gym.domain.money import format_money
from gym.domain.rules import period_end_date
from gym.services import payments as payments_service
from gym.services import plans as plans_service
from gym.services.errors import ServiceError
from gym.ui.widgets.common import Card, primary_button, secondary_button
from gym.ui.widgets.inputs import Field


class ChargeDialog(QDialog):
    """Cobra un plan de la categoria del socio."""

    def __init__(self, member: Member, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.member = member
        self.setWindowTitle(f"Cobrar · {member.name}")
        self.setModal(True)
        self.setMinimumWidth(440)

        self.plan_input = QComboBox(self)
        self._plans = {}
        for plan in plans_service.list_plans(member.plan_category_id):
            label = f"{plan.name} ({format_money(plan.price_cents)})"
            self.plan_input.addItem(label, plan.id)
            self._plans[plan.id] = plan
        payment = member.recent_payment
        if payment is not None:
            index = self.plan_input.findData(payment.plan_id)
            if index >= 0:
                self.plan_input.setCurrentIndex(index)
        self.plan_input.currentIndexChanged.connect(self._update_preview)
        self.plan_field = Field("Plan", self.plan_input, self)

        self.start_input = QDateEdit(self)
        self.start_input.setCalendarPopup(True)
        self.start_input.setDisplayFormat("dd/MM/yyyy")
        self.start_input.setEnabled(False)

        suggested = self._suggested_start()
        self.start_input.setDate(QDate(suggested.year, suggested.month, suggested.day))
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
        preview_card = Card(self)
        preview_card.body.addWidget(self.preview)

        self.save_button = primary_button("Cobrar", self.accept)
        self.save_button.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.plan_field)
        layout.addWidget(self.start_field)
        layout.addWidget(preview_card)
        layout.addLayout(buttons)

        self._update_preview()

    def _on_custom_start(self, checked: bool) -> None:
        self.start_input.setEnabled(checked)
        self._update_preview()

    def _suggested_start(self) -> date:
        payment = self.member.recent_payment
        if payment and payment.end_date.date() >= date.today():
            return payment.end_date.date() + timedelta(days=1)
        return date.today()

    def _start_date(self) -> date:
        if self.custom_start.isChecked():
            qdate = self.start_input.date()
            return date(qdate.year(), qdate.month(), qdate.day())
        return self._suggested_start()

    def _update_preview(self) -> None:
        plan_id = self.plan_input.currentData()
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

    def accept(self) -> None:
        self.plan_field.clear_error()
        plan_id = self.plan_input.currentData()
        if plan_id is None:
            self.plan_field.show_error("Configura al menos un plan en Planes.")
            return

        start = self._start_date() if self.custom_start.isChecked() else None
        try:
            payments_service.charge(self.member.id, plan_id, start)
        except ServiceError as error:
            self.plan_field.show_error(str(error))
            return
        super().accept()
