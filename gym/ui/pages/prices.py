"""Catalogo de precios: tipos de membresia y sus duraciones."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Duration, MembershipType
from gym.domain.enums import DurationUnit
from gym.domain.money import format_money
from gym.services import memberships as service
from gym.services.errors import ServiceError, ValidationError
from gym.ui.main_window import Page
from gym.ui.widgets.common import (
    PageHeader,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import alert, confirm
from gym.ui.widgets.inputs import Field, MoneyInput
from gym.ui.widgets.table import Column, PagedTable


class MembershipTypeDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, membership_type: MembershipType | None = None
    ):
        super().__init__(parent)
        self.membership_type = membership_type
        self.setWindowTitle("Editar tipo" if membership_type else "Nuevo tipo de membresía")
        self.setModal(True)
        self.setMinimumWidth(380)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Por ejemplo: General, Estudiante")
        if membership_type:
            self.name_input.setText(membership_type.name)
        self.name_field = Field("Nombre", self.name_input, self)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        save = primary_button("Guardar", self.accept)
        save.setDefault(True)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.name_field)
        layout.addLayout(buttons)

    def accept(self) -> None:
        self.name_field.clear_error()
        try:
            if self.membership_type is None:
                service.create_membership_type(self.name_input.text())
            else:
                service.rename_membership_type(self.membership_type.id, self.name_input.text())
        except ValidationError as error:
            self.name_field.show_error(error.errors.get("name", str(error)))
            return
        except ServiceError as error:
            self.name_field.show_error(str(error))
            return
        super().accept()


class DurationDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, duration: Duration | None = None) -> None:
        super().__init__(parent)
        self.duration = duration
        self.setWindowTitle("Editar duración" if duration else "Nueva duración")
        self.setModal(True)
        self.setMinimumWidth(420)

        self.type_input = QComboBox(self)
        for membership_type in service.list_membership_types():
            self.type_input.addItem(membership_type.name, membership_type.id)
        self.type_field = Field("Tipo de membresía", self.type_input, self)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Por ejemplo: Mensual, 2 Semanas")
        self.name_field = Field("Nombre", self.name_input, self)

        self.amount_input = QSpinBox(self)
        self.amount_input.setRange(1, 365)
        self.amount_input.setValue(1)

        self.unit_input = QComboBox(self)
        for unit in DurationUnit:
            self.unit_input.addItem(unit.label(2), unit.value)

        amount_box = QWidget(self)
        amount_row = QHBoxLayout(amount_box)
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.setSpacing(8)
        amount_row.addWidget(self.amount_input, 1)
        amount_row.addWidget(self.unit_input, 2)
        self.amount_field = Field("Duración", amount_box, self)

        self.price_input = MoneyInput(self)
        self.price_field = Field("Precio", self.price_input, self)

        if duration is not None:
            self._load(duration)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        save = primary_button("Guardar", self.accept)
        save.setDefault(True)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.type_field)
        layout.addWidget(self.name_field)
        layout.addWidget(self.amount_field)
        layout.addWidget(self.price_field)
        layout.addLayout(buttons)

    def _load(self, duration: Duration) -> None:
        index = self.type_input.findData(duration.membership_type_id)
        if index >= 0:
            self.type_input.setCurrentIndex(index)
        self.type_input.setEnabled(False)
        self.name_input.setText(duration.name)
        self.amount_input.setValue(duration.amount)
        unit_index = self.unit_input.findData(duration.unit.value)
        if unit_index >= 0:
            self.unit_input.setCurrentIndex(unit_index)
        self.price_input.set_cents(duration.price_cents)

    def accept(self) -> None:
        for field in (self.type_field, self.name_field, self.amount_field, self.price_field):
            field.clear_error()

        if self.type_input.currentData() is None:
            self.type_field.show_error("Crea primero un tipo de membresía.")
            return
        if not self.price_input.is_valid():
            self.price_field.show_error("Escribe un precio válido, por ejemplo 400.00")
            return

        unit = DurationUnit(self.unit_input.currentData())
        try:
            if self.duration is None:
                service.create_duration(
                    self.type_input.currentData(),
                    self.name_input.text(),
                    self.amount_input.value(),
                    unit,
                    self.price_input.cents(),
                )
            else:
                service.update_duration(
                    self.duration.id,
                    self.name_input.text(),
                    self.amount_input.value(),
                    unit,
                    self.price_input.cents(),
                )
        except ValidationError as error:
            mapping = {
                "name": self.name_field,
                "amount": self.amount_field,
                "price": self.price_field,
            }
            for key, message in error.errors.items():
                field = mapping.get(key)
                if field:
                    field.show_error(message)
            return
        except ServiceError as error:
            self.name_field.show_error(str(error))
            return
        super().accept()


class PricesPage(Page):
    title = "Precios"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window

        header = PageHeader(
            "Precios",
            "Tipos de membresía y sus duraciones. "
            "Cambiar un precio no altera pagos ya registrados.",
        )
        header.add_action(secondary_button("Nuevo tipo", self.create_type))
        header.add_action(primary_button("Nueva duración", self.create_duration))

        self.types_table = PagedTable[MembershipType](
            columns=[
                Column("Tipo de membresía", lambda t: t.name, stretch=True),
                Column(
                    "Duraciones",
                    lambda t: len(t.durations),
                    width=110,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
            ],
            page_size=50,
            empty_text="No hay tipos de membresía. Crea el primero.",
        )
        self.types_table.row_activated.connect(lambda _: self.edit_type())

        type_buttons = QHBoxLayout()
        type_buttons.addWidget(secondary_button("Editar tipo", self.edit_type))
        type_buttons.addWidget(danger_button("Eliminar tipo", self.delete_type))
        type_buttons.addStretch(1)

        self.durations_table = PagedTable[Duration](
            columns=[
                Column("Tipo", lambda d: d.membership_type.name, width=140),
                Column("Duración", lambda d: d.name, stretch=True),
                Column(
                    "Equivale a",
                    lambda d: f"{d.amount} {d.unit.label(d.amount)}",
                    width=130,
                ),
                Column(
                    "Precio",
                    lambda d: format_money(d.price_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            page_size=50,
            empty_text="No hay duraciones configuradas.",
        )
        self.durations_table.row_activated.connect(lambda _: self.edit_duration())

        duration_buttons = QHBoxLayout()
        duration_buttons.addWidget(secondary_button("Editar duración", self.edit_duration))
        duration_buttons.addWidget(danger_button("Eliminar duración", self.delete_duration))
        duration_buttons.addStretch(1)

        tables = QHBoxLayout()
        tables.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.types_table, 1)
        left.addLayout(type_buttons)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(self.durations_table, 1)
        right.addLayout(duration_buttons)

        tables.addLayout(left, 2)
        tables.addLayout(right, 3)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addLayout(tables, 1)

    def refresh(self) -> None:
        types = service.list_membership_types()
        self.types_table.set_data(types, len(types))
        durations = service.list_durations()
        self.durations_table.set_data(durations, len(durations))

    def create_type(self) -> None:
        if MembershipTypeDialog(self).exec():
            self.window_ref.notify_success("Tipo de membresía creado.")
            self.refresh()

    def edit_type(self) -> None:
        membership_type = self.types_table.selected_record()
        if membership_type is None:
            self.window_ref.notify("Selecciona un tipo de la tabla primero.")
            return
        if MembershipTypeDialog(self, membership_type).exec():
            self.window_ref.notify_success("Tipo actualizado.")
            self.refresh()

    def delete_type(self) -> None:
        membership_type = self.types_table.selected_record()
        if membership_type is None:
            self.window_ref.notify("Selecciona un tipo de la tabla primero.")
            return

        if not confirm(
            self,
            "Eliminar tipo",
            f"¿Eliminar el tipo «{membership_type.name}»?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_membership_type(membership_type.id)
        except ServiceError as error:
            alert(self, "No se puede eliminar", str(error))
            return

        self.window_ref.notify_success("Tipo eliminado.")
        self.refresh()

    def create_duration(self) -> None:
        if not service.list_membership_types():
            self.window_ref.notify_error("Crea primero un tipo de membresía.")
            return
        if DurationDialog(self).exec():
            self.window_ref.notify_success("Duración creada.")
            self.refresh()

    def edit_duration(self) -> None:
        duration = self.durations_table.selected_record()
        if duration is None:
            self.window_ref.notify("Selecciona una duración de la tabla primero.")
            return
        if DurationDialog(self, duration).exec():
            self.window_ref.notify_success("Duración actualizada.")
            self.refresh()

    def delete_duration(self) -> None:
        duration = self.durations_table.selected_record()
        if duration is None:
            self.window_ref.notify("Selecciona una duración de la tabla primero.")
            return

        if not confirm(
            self,
            "Eliminar duración",
            f"¿Eliminar la duración «{duration.name}»?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_duration(duration.id)
        except ServiceError as error:
            alert(self, "No se puede eliminar", str(error))
            return

        self.window_ref.notify_success("Duración eliminada.")
        self.refresh()
