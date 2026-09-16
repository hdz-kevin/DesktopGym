"""Catalogo de categorias y planes."""

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

from gym.data.models import Plan, PlanCategory
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


class PlanCategoryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, category: PlanCategory | None = None):
        super().__init__(parent)
        self.category = category
        self.setWindowTitle("Editar categoría" if category else "Nueva categoría de planes")
        self.setModal(True)
        self.setMinimumWidth(380)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Por ejemplo: General, Estudiante")
        if category:
            self.name_input.setText(category.name)
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
            if self.category is None:
                service.create_plan_category(self.name_input.text())
            else:
                service.rename_plan_category(self.category.id, self.name_input.text())
        except ValidationError as error:
            self.name_field.show_error(error.errors.get("name", str(error)))
            return
        except ServiceError as error:
            self.name_field.show_error(str(error))
            return
        super().accept()


class PlanDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, plan: Plan | None = None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("Editar plan" if plan else "Nuevo plan")
        self.setModal(True)
        self.setMinimumWidth(420)

        self.category_input = QComboBox(self)
        for category in service.list_plan_categories():
            self.category_input.addItem(category.name, category.id)
        self.category_field = Field("Categoría de planes", self.category_input, self)

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

        if plan is not None:
            self._load(plan)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cancelar", self.reject))
        save = primary_button("Guardar", self.accept)
        save.setDefault(True)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.category_field)
        layout.addWidget(self.name_field)
        layout.addWidget(self.amount_field)
        layout.addWidget(self.price_field)
        layout.addLayout(buttons)

    def _load(self, plan: Plan) -> None:
        index = self.category_input.findData(plan.plan_category_id)
        if index >= 0:
            self.category_input.setCurrentIndex(index)
        self.category_input.setEnabled(False)
        self.name_input.setText(plan.name)
        self.amount_input.setValue(plan.amount)
        unit_index = self.unit_input.findData(plan.unit.value)
        if unit_index >= 0:
            self.unit_input.setCurrentIndex(unit_index)
        self.price_input.set_cents(plan.price_cents)

    def accept(self) -> None:
        for field in (self.category_field, self.name_field, self.amount_field, self.price_field):
            field.clear_error()

        if self.category_input.currentData() is None:
            self.category_field.show_error("Crea primero una categoría de planes.")
            return
        if not self.price_input.is_valid():
            self.price_field.show_error("Escribe un precio válido, por ejemplo 400.00")
            return

        unit = DurationUnit(self.unit_input.currentData())
        try:
            if self.plan is None:
                service.create_plan(
                    self.category_input.currentData(),
                    self.name_input.text(),
                    self.amount_input.value(),
                    unit,
                    self.price_input.cents(),
                )
            else:
                service.update_plan(
                    self.plan.id,
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


class PlansPage(Page):
    title = "Planes"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window

        header = PageHeader(
            "Planes",
            "Planes agrupados por categorías.",
        )

        # Categories table
        self.categories_table = PagedTable[PlanCategory](
            columns=[
                Column("Categoría", lambda t: t.name, stretch=True),
                Column(
                    "Planes",
                    lambda t: len(t.plans),
                    width=110,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
            ],
            page_size=50,
            empty_text="No hay categorías de planes. Crea la primera.",
            paginated=False,
        )
        self.categories_table.row_activated.connect(lambda _: self.edit_category())

        category_buttons = QHBoxLayout()
        category_buttons.addStretch(1)
        category_buttons.addWidget(danger_button("Eliminar categoría", self.delete_category))
        category_buttons.addWidget(secondary_button("Editar categoría", self.edit_category))
        category_buttons.addWidget(primary_button("Nueva categoría", self.create_category))

        # Plans table
        self.plans_table = PagedTable[Plan](
            columns=[
                Column("Categoría", lambda d: d.plan_category.name, width=140),
                Column("Nombre", lambda d: d.name, stretch=True),
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
            empty_text="No hay planes configurados.",
            paginated=False,
        )
        self.plans_table.row_activated.connect(lambda _: self.edit_plan())

        plan_buttons = QHBoxLayout()
        plan_buttons.addStretch(1)
        plan_buttons.addWidget(danger_button("Eliminar plan", self.delete_plan))
        plan_buttons.addWidget(secondary_button("Editar plan", self.edit_plan))
        plan_buttons.addWidget(primary_button("Nuevo plan", self.create_plan))

        tables = QHBoxLayout()
        tables.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.categories_table, 1)
        left.addLayout(category_buttons)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(self.plans_table, 1)
        right.addLayout(plan_buttons)

        tables.addLayout(left, 2)
        tables.addLayout(right, 3)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.addWidget(header)
        layout.addLayout(tables, 1)
        layout.addStretch(1)

    def refresh(self) -> None:
        categories = service.list_plan_categories()
        self.categories_table.set_data(categories, len(categories))
        plans = service.list_plans()
        self.plans_table.set_data(plans, len(plans))

    def create_category(self) -> None:
        if PlanCategoryDialog(self).exec():
            self.window_ref.notify_success("Categoría de planes creada.")
            self.refresh()

    def edit_category(self) -> None:
        category = self.categories_table.selected_record()
        if category is None:
            self.window_ref.notify("Selecciona una categoría de la tabla primero.")
            return
        if PlanCategoryDialog(self, category).exec():
            self.window_ref.notify_success("Categoría actualizada.")
            self.refresh()

    def delete_category(self) -> None:
        category = self.categories_table.selected_record()
        if category is None:
            self.window_ref.notify("Selecciona una categoría de la tabla primero.")
            return

        if not confirm(
            self,
            "Eliminar categoría",
            f"¿Eliminar la categoría «{category.name}»?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_plan_category(category.id)
        except ServiceError as error:
            alert(self, "No se puede eliminar", str(error))
            return

        self.window_ref.notify_success("Categoría eliminada.")
        self.refresh()

    def create_plan(self) -> None:
        if not service.list_plan_categories():
            self.window_ref.notify_error("Crea primero una categoría de planes.")
            return
        if PlanDialog(self).exec():
            self.window_ref.notify_success("Plan creado.")
            self.refresh()

    def edit_plan(self) -> None:
        plan = self.plans_table.selected_record()
        if plan is None:
            self.window_ref.notify("Selecciona un plan de la tabla primero.")
            return
        if PlanDialog(self, plan).exec():
            self.window_ref.notify_success("Plan actualizado.")
            self.refresh()

    def delete_plan(self) -> None:
        plan = self.plans_table.selected_record()
        if plan is None:
            self.window_ref.notify("Selecciona un plan de la tabla primero.")
            return

        if not confirm(
            self,
            "Eliminar plan",
            f"¿Eliminar el plan «{plan.name}»?",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_plan(plan.id)
        except ServiceError as error:
            alert(self, "No se puede eliminar", str(error))
            return

        self.window_ref.notify_success("Plan eliminado.")
        self.refresh()
