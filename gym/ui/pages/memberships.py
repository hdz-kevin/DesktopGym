"""Pantalla de membresias: alta, renovacion e historial."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from gym.data.models import Membership
from gym.domain.dates import humanize_delta
from gym.domain.enums import MembershipStatus
from gym.services import memberships as service
from gym.services.errors import ServiceError
from gym.ui.dialogs.membership_form import MembershipFormDialog, RenewMembershipDialog
from gym.ui.dialogs.membership_history import MembershipHistoryDialog
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
    MembershipStatus.ACTIVE: SUCCESS,
    MembershipStatus.EXPIRED: DANGER,
}

FILTERS: list[tuple[MembershipStatus | None, str]] = [
    (None, "Todas"),
    (MembershipStatus.ACTIVE, "Activas"),
    (MembershipStatus.EXPIRED, "Vencidas"),
]


def _expiry_text(membership: Membership) -> str:
    payment = membership.recent_payment
    if payment is None:
        return "—"
    delta = humanize_delta(payment.end_date)
    if membership.status is MembershipStatus.ACTIVE:
        return f"en {delta}"
    return f"hace {delta}"


class MembershipsPage(Page):
    title = "Membresías"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._search = ""
        self._status: MembershipStatus | None = None

        header = PageHeader("Membresías", "Altas, renovaciones e historial de pagos")

        self.stat_total = StatCard("Total")
        self.stat_active = StatCard("Activas")
        self.stat_expired = StatCard("Vencidas")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_total, self.stat_active, self.stat_expired):
            stats.addWidget(card)

        self.search_box = SearchBox("Buscar por socio o código...")
        self.search_box.setFixedWidth(320)
        self.search_box.search_changed.connect(self._on_search)

        self.chips = FilterChips(FILTERS)
        self.chips.changed.connect(self._on_filter)

        controls = ControlsRow()
        controls.addWidget(self.search_box)
        controls.addWidget(self.chips, 1)
        controls.addWidget(secondary_button("Renovar", self.renew_selected))
        controls.addWidget(primary_button("Nueva membresía", self.create_membership))

        self.table = PagedTable[Membership](
            columns=[
                Column("Código", lambda m: m.member.code, width=90),
                Column("Socio", lambda m: m.member.name, stretch=True),
                Column("Plan", lambda m: m.current_plan_label, width=200),
                Column("Vigencia", _expiry_text, width=220),
                Column(
                    "Estado",
                    lambda m: m.status.label(),
                    width=110,
                    color=lambda m: STATUS_COLORS.get(m.status),
                ),
            ],
            page_size=25,
            empty_text="No hay membresías registradas todavía.",
        )
        self.table.row_activated.connect(lambda m: self._show_history(m.id))
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
        rows, total = service.list_memberships(
            search=self._search,
            status=self._status,
            offset=self.table.offset,
            limit=self.table.page_size,
        )
        self.table.set_data(rows, total)

    def load_stats(self) -> None:
        stats = service.membership_stats()
        self.stat_total.set_value(str(stats.total))
        self.stat_active.set_value(str(stats.active))
        self.stat_expired.set_value(str(stats.expired))

    def _on_search(self, text: str) -> None:
        self._search = text
        self.table.reset_page()
        self.load()

    def _on_filter(self, status: MembershipStatus | None) -> None:
        self._status = status
        self.table.reset_page()
        self.load()

    def create_membership(self) -> None:
        if not service.list_plans():
            self.window_ref.notify_error("Primero configura categorías y planes en Precios (F5).")
            return

        dialog = MembershipFormDialog(self)
        if dialog.exec():
            self.window_ref.notify_success("Membresía registrada.")
            self.refresh()

    def renew_selected(self) -> None:
        membership = self._require_selection()
        if membership is None:
            return

        try:
            dialog = RenewMembershipDialog(membership, self)
        except ServiceError as error:
            self.window_ref.notify_error(str(error))
            return

        if dialog.exec():
            self.window_ref.notify_success("Membresía renovada.")
            self.refresh()

    def _show_history(self, membership_id: int) -> None:
        dialog = MembershipHistoryDialog(membership_id, self)
        dialog.exec()
        if dialog.changed:
            self.refresh()

    def _require_selection(self) -> Membership | None:
        membership = self.table.selected_record()
        if membership is None:
            self.window_ref.notify("Selecciona una membresía de la tabla primero.")
        return membership
