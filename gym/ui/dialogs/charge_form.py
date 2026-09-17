"""Renovacion de un plan del socio."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget

from gym.data.models import Member
from gym.services import payments as payments_service
from gym.services.errors import ServiceError
from gym.ui.widgets.common import primary_button, secondary_button
from gym.ui.widgets.plan_charge import PlanChargeFields


class ChargeDialog(QDialog):
    """Renueva un plan de la categoria del socio."""

    def __init__(self, member: Member, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.member = member
        self.setWindowTitle(f"Renovar · {member.name}")
        self.setModal(True)
        self.setMinimumWidth(440)

        payment = member.recent_payment
        self.charge_fields = PlanChargeFields(
            self,
            category_id=member.plan_category_id,
            suggested_start=self._suggested_start(),
            selected_plan_id=payment.plan_id if payment is not None else None,
        )
        self.plan_input = self.charge_fields.plan_input
        self.start_input = self.charge_fields.start_input
        self.preview = self.charge_fields.preview

        self.save_button = primary_button("Renovar", self.accept)
        self.save_button.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.charge_fields)
        layout.addLayout(buttons)

    def _suggested_start(self) -> date:
        payment = self.member.recent_payment
        if payment and payment.end_date.date() >= date.today():
            return payment.end_date.date() + timedelta(days=1)
        return date.today()

    def accept(self) -> None:
        self.charge_fields.plan_field.clear_error()
        plan_id = self.charge_fields.plan_id()
        if plan_id is None:
            self.charge_fields.plan_field.show_error("Configura al menos un plan en Planes.")
            return

        try:
            payments_service.charge(self.member.id, plan_id, self.charge_fields.explicit_start())
        except ServiceError as error:
            self.charge_fields.plan_field.show_error(str(error))
            return
        super().accept()
