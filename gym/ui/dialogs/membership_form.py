"""Alta y renovacion de membresias."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Membership
from gym.domain.dates import format_date
from gym.domain.money import format_money
from gym.domain.rules import period_end_date
from gym.services import memberships as service
from gym.services.errors import ServiceError
from gym.ui.widgets.common import Card, primary_button, secondary_button
from gym.ui.widgets.inputs import Field, SearchBox


def _plan_options(combo: QComboBox) -> dict[int, object]:
    """Llena el combo con los planes y devuelve el catalogo por id.

    Se conserva el catalogo en memoria para no reconsultar la base cada vez que
    el usuario mueve la fecha y se recalcula la vista previa.
    """
    combo.clear()
    catalog = {}
    for plan in service.list_plans():
        label = f"{plan.plan_category.name} · {plan.name} ({format_money(plan.price_cents)})"
        combo.addItem(label, plan.id)
        catalog[plan.id] = plan
    return catalog


class MembershipFormDialog(QDialog):
    """Alta de membresia: elegir socio, plan y fecha de inicio."""

    def __init__(self, parent: QWidget | None = None, member_id: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva membresía")
        self.setModal(True)
        self.setMinimumWidth(480)

        self.membership_id: int | None = None
        self._member_id: int | None = member_id

        self.search_box = SearchBox("Buscar socio por nombre o código...")
        self.search_box.search_changed.connect(self._search_members)

        self.results = QListWidget(self)
        self.results.setMaximumHeight(150)
        self.results.setVisible(False)
        self.results.itemClicked.connect(self._select_member)

        self.selected_label = QLabel("Ningún socio seleccionado", self)
        self.selected_label.setObjectName("muted")

        member_box = QWidget(self)
        member_layout = QVBoxLayout(member_box)
        member_layout.setContentsMargins(0, 0, 0, 0)
        member_layout.setSpacing(6)
        member_layout.addWidget(self.search_box)
        member_layout.addWidget(self.results)
        member_layout.addWidget(self.selected_label)
        self.member_field = Field("Socio", member_box, self)

        self.plan_input = QComboBox(self)
        self._plans = _plan_options(self.plan_input)
        self.plan_input.currentIndexChanged.connect(self._update_preview)
        self.plan_field = Field("Plan", self.plan_input, self)

        self.start_input = QDateEdit(self)
        self.start_input.setCalendarPopup(True)
        self.start_input.setDisplayFormat("dd/MM/yyyy")
        self.start_input.setDate(QDate.currentDate())
        self.start_input.dateChanged.connect(self._update_preview)
        self.start_field = Field("Inicio", self.start_input, self)

        self.preview = QLabel("", self)
        self.preview.setObjectName("muted")
        preview_card = Card(self)
        preview_card.body.addWidget(self.preview)

        self.save_button = primary_button("Registrar membresía", self.accept)
        self.save_button.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.member_field)
        layout.addWidget(self.plan_field)
        layout.addWidget(self.start_field)
        layout.addWidget(preview_card)
        layout.addLayout(buttons)

        if member_id is not None:
            self._set_member(member_id, "")
        self._update_preview()

    def _search_members(self, term: str) -> None:
        self.results.clear()
        for member in service.search_members(term):
            item = QListWidgetItem(f"{member.name}  ·  {member.code}")
            item.setData(Qt.ItemDataRole.UserRole, (member.id, member.name))
            self.results.addItem(item)
        self.results.setVisible(self.results.count() > 0)

    def _select_member(self, item: QListWidgetItem) -> None:
        member_id, name = item.data(Qt.ItemDataRole.UserRole)
        self._set_member(member_id, name)

    def _set_member(self, member_id: int, name: str) -> None:
        self._member_id = member_id
        self.selected_label.setText(f"Socio seleccionado: {name}" if name else "Socio seleccionado")
        self.member_field.clear_error()

    def _selected_plan_id(self) -> int | None:
        return self.plan_input.currentData()

    def _start_date(self) -> date:
        qdate = self.start_input.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _update_preview(self) -> None:
        plan_id = self._selected_plan_id()
        if plan_id is None:
            self.preview.setText("No hay planes configurados. Ve a Precios (F5).")
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
        self.member_field.clear_error()
        self.plan_field.clear_error()

        if self._member_id is None:
            self.member_field.show_error("Selecciona un socio.")
            return

        plan_id = self._selected_plan_id()
        if plan_id is None:
            self.plan_field.show_error("Configura al menos un plan en Precios.")
            return

        try:
            self.membership_id = service.create_membership(
                self._member_id, plan_id, self._start_date()
            )
        except ServiceError as error:
            self.member_field.show_error(str(error))
            return
        super().accept()


class RenewMembershipDialog(QDialog):
    """Renovacion: agrega un periodo nuevo a una membresia existente."""

    def __init__(self, membership: Membership, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.membership = membership
        self.setWindowTitle(f"Renovar · {membership.member.name}")
        self.setModal(True)
        self.setMinimumWidth(440)

        self.plan_input = QComboBox(self)
        _plan_options(self.plan_input)
        payment = membership.recent_payment
        if payment is not None:
            index = self.plan_input.findData(payment.plan_id)
            if index >= 0:
                self.plan_input.setCurrentIndex(index)
        self.plan_field = Field("Categoría y plan", self.plan_input, self)

        self.start_input = QDateEdit(self)
        self.start_input.setCalendarPopup(True)
        self.start_input.setDisplayFormat("dd/MM/yyyy")
        self.start_input.setEnabled(False)

        suggested = self._suggested_start()
        self.start_input.setDate(QDate(suggested.year, suggested.month, suggested.day))

        self.custom_start = QCheckBox("Elegir otra fecha de inicio", self)
        self.custom_start.toggled.connect(self.start_input.setEnabled)

        start_box = QWidget(self)
        start_layout = QVBoxLayout(start_box)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.setSpacing(6)
        start_layout.addWidget(self.custom_start)
        start_layout.addWidget(self.start_input)
        self.start_field = Field("Inicio", start_box, self)

        self.save_button = primary_button("Renovar", self.accept)
        self.save_button.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.plan_field)
        layout.addWidget(self.start_field)
        layout.addLayout(buttons)

    def _suggested_start(self) -> date:
        """Continua desde el vencimiento si la membresia sigue vigente."""
        payment = self.membership.recent_payment
        if payment and payment.end_date.date() >= date.today():
            return payment.end_date.date() + timedelta(days=1)
        return date.today()

    def accept(self) -> None:
        self.plan_field.clear_error()
        plan_id = self.plan_input.currentData()
        if plan_id is None:
            self.plan_field.show_error("Configura al menos un plan en Precios.")
            return

        start = None
        if self.custom_start.isChecked():
            qdate = self.start_input.date()
            start = date(qdate.year(), qdate.month(), qdate.day())

        try:
            service.renew_membership(self.membership.id, plan_id, start)
        except ServiceError as error:
            self.plan_field.show_error(str(error))
            return
        super().accept()
