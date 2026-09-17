"""Pantalla de socios: ficha, renovacion, historial y filtros."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from gym.data.models import Member
from gym.domain.dates import humanize_delta
from gym.domain.enums import MemberStatus
from gym.services import members as service
from gym.services import plans as plans_service
from gym.ui.dialogs.charge_form import ChargeDialog
from gym.ui.dialogs.member_form import MemberFormDialog
from gym.ui.dialogs.member_profile import MemberProfileDialog
from gym.ui.main_window import Page
from gym.ui.theme import DANGER, SUCCESS
from gym.ui.widgets.common import (
    ControlsRow,
    FilterChips,
    PageHeader,
    StatCard,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.inputs import SearchBox
from gym.ui.widgets.table import Column, PagedTable

STATUS_COLORS = {
    MemberStatus.ACTIVE: SUCCESS,
    MemberStatus.EXPIRED: DANGER,
}

FILTERS: list[tuple[MemberStatus | None, str]] = [
    (None, "Todos"),
    (MemberStatus.ACTIVE, "Activos"),
    (MemberStatus.EXPIRED, "Vencidos"),
]


def _expiry_text(member: Member) -> str:
    payment = member.recent_payment
    if payment is None:
        return "—"
    delta = humanize_delta(payment.end_date)
    if member.status is MemberStatus.ACTIVE:
        return f"en {delta}"
    return f"hace {delta}"


def _plan_name(member: Member) -> str:
    plan = member.current_plan
    return plan.name if plan else "—"


class MembersPage(Page):
    title = "Socios"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._search = ""
        self._status: MemberStatus | None = None

        header = PageHeader("Socios", "Gestión de socios e historial de pagos")

        self.stat_total = StatCard("Total")
        self.stat_active = StatCard("Activos")
        self.stat_expired = StatCard("Vencidos")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_total, self.stat_active, self.stat_expired):
            stats.addWidget(card)

        self.search_box = SearchBox("Buscar por nombre o código...")
        self.search_box.setFixedWidth(320)
        self.search_box.search_changed.connect(self._on_search)

        self.chips = FilterChips(FILTERS)
        self.chips.changed.connect(self._on_filter)

        controls = ControlsRow()
        controls.addWidget(self.search_box)
        controls.addWidget(self.chips, 1)
        controls.addWidget(secondary_button("Editar", self.edit_selected))
        controls.addWidget(secondary_button("Ver Perfil", self.show_profile))
        controls.addWidget(secondary_button("Renovar", self.charge_selected))
        controls.addWidget(primary_button("Nuevo socio", self.create_member))

        self.table = PagedTable[Member](
            columns=[
                Column("Código", lambda m: m.code, width=90),
                Column("Nombre", lambda m: m.name, stretch=True),
                Column("Categoría", lambda m: m.plan_category.name, width=130),
                Column("Plan", _plan_name, width=130),
                Column("Vigencia", _expiry_text, width=180),
                Column(
                    "Estado",
                    lambda m: m.status.label(),
                    width=110,
                    color=lambda m: STATUS_COLORS.get(m.status),
                ),
            ],
            page_size=25,
            empty_text="No hay socios que coincidan con la búsqueda.",
        )
        self.table.row_activated.connect(self.show_profile)
        self.table.page_changed.connect(lambda _: self.load())

        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.addWidget(header)
        layout.addLayout(stats)
        layout.addLayout(controls)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.load()
        self.load_stats()

    def load(self) -> None:
        rows, total = service.list_members(
            search=self._search,
            status=self._status,
            offset=self.table.offset,
            limit=self.table.page_size,
        )
        self.table.set_data(rows, total)

    def load_stats(self) -> None:
        stats = service.member_stats()
        self.stat_total.set_value(str(stats.total))
        self.stat_active.set_value(str(stats.active))
        self.stat_expired.set_value(str(stats.expired))

    def _on_search(self, text: str) -> None:
        self._search = text
        self.table.reset_page()
        self.load()

    def _on_filter(self, status: MemberStatus | None) -> None:
        self._status = status
        self.table.reset_page()
        self.load()

    def create_member(self) -> None:
        if not plans_service.list_plan_categories():
            self.window_ref.notify_error("Primero configura categorías en Planes (F4).")
            return
        dialog = MemberFormDialog(self)
        if dialog.exec():
            self.window_ref.notify_success("Socio registrado correctamente.")
            self.refresh()

    def edit_selected(self) -> None:
        member = self._require_selection()
        if member is None:
            return
        dialog = MemberFormDialog(self, member)
        if dialog.exec():
            self.window_ref.notify_success("Socio actualizado.")
            self.refresh()

    def charge_selected(self) -> None:
        member = self._require_selection()
        if member is None:
            return
        if not plans_service.list_plans(member.plan_category_id):
            self.window_ref.notify_error(
                "Esta categoría no tiene planes. Configúralos en Planes (F4)."
            )
            return
        dialog = ChargeDialog(member, self)
        if dialog.exec():
            self.window_ref.notify_success("Renovación aplicada.")
            self.refresh()

    def show_profile(self, member: Member | None = None) -> None:
        if member is None:
            member = self._require_selection()
            if member is None:
                return
        MemberProfileDialog(member, self).exec()

    def _require_selection(self) -> Member | None:
        member = self.table.selected_record()
        if member is None:
            self.window_ref.notify("Selecciona un socio de la tabla primero.")
        return member
