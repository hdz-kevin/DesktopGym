"""Pantalla de socios: alta, edicion, filtros y perfil."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from gym.data.models import Member
from gym.domain.dates import format_date
from gym.domain.enums import MemberStatus
from gym.services import members as service
from gym.services.errors import ServiceError
from gym.ui.dialogs.member_form import MemberFormDialog
from gym.ui.dialogs.member_profile import MemberProfileDialog
from gym.ui.main_window import Page
from gym.ui.theme import DANGER, SUCCESS, TEXT_MUTED
from gym.ui.widgets.common import (
    FilterChips,
    PageHeader,
    StatCard,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import confirm
from gym.ui.widgets.inputs import SearchBox
from gym.ui.widgets.table import Column, PagedTable

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    MemberStatus.ACTIVE: SUCCESS,
    MemberStatus.EXPIRED: DANGER,
    MemberStatus.NO_MEMBERSHIP: TEXT_MUTED,
}

FILTERS: list[tuple[MemberStatus | None, str]] = [
    (None, "Todos"),
    (MemberStatus.ACTIVE, "Activos"),
    (MemberStatus.EXPIRED, "Vencidos"),
    (MemberStatus.NO_MEMBERSHIP, "Sin membresía"),
]


class MembersPage(Page):
    title = "Socios"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self._search = ""
        self._status: MemberStatus | None = None

        header = PageHeader("Socios", "Alta, consulta y edición de socios")

        self.stat_total = StatCard("Total")
        self.stat_active = StatCard("Activos")
        self.stat_expired = StatCard("Vencidos")
        self.stat_none = StatCard("Sin membresía")

        stats = QHBoxLayout()
        stats.setSpacing(12)
        for card in (self.stat_total, self.stat_active, self.stat_expired, self.stat_none):
            stats.addWidget(card)

        self.search_box = SearchBox("Buscar por nombre o código...")
        self.search_box.setFixedWidth(320)
        self.search_box.search_changed.connect(self._on_search)

        self.chips = FilterChips(FILTERS)
        self.chips.changed.connect(self._on_filter)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.addWidget(self.search_box)
        controls.addWidget(self.chips, 1)
        controls.addWidget(secondary_button("Editar", self.edit_selected))
        controls.addWidget(danger_button("Eliminar", self.delete_selected))
        controls.addWidget(primary_button("Nuevo socio", self.create_member))

        self.table = PagedTable[Member](
            columns=[
                Column("Código", lambda m: m.code, width=90),
                Column("Nombre", lambda m: m.name, stretch=True),
                Column("Género", lambda m: m.gender.label(), width=110),
                Column(
                    "Edad",
                    lambda m: m.age if m.age is not None else "—",
                    width=70,
                    align=Qt.AlignmentFlag.AlignCenter,
                ),
                Column(
                    "Estado",
                    lambda m: m.status.label(),
                    width=140,
                    color=lambda m: STATUS_COLORS.get(m.status),
                ),
                Column("Socio desde", lambda m: format_date(m.created_at), width=130),
            ],
            page_size=25,
            empty_text="No hay socios que coincidan con la búsqueda.",
        )
        self.table.row_activated.connect(self._show_profile)
        self.table.page_changed.connect(lambda _: self.load())

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
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
        self.stat_none.set_value(str(stats.without_membership))

    def _on_search(self, text: str) -> None:
        self._search = text
        self.table.reset_page()
        self.load()

    def _on_filter(self, status: MemberStatus | None) -> None:
        self._status = status
        self.table.reset_page()
        self.load()

    def create_member(self) -> None:
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

    def _show_profile(self, member: Member) -> None:
        MemberProfileDialog(member, self).exec()

    def delete_selected(self) -> None:
        member = self._require_selection()
        if member is None:
            return

        if not confirm(
            self,
            "Eliminar socio",
            f"¿Eliminar a {member.name}?\n\nEsta acción no se puede deshacer.",
            confirm_text="Eliminar",
            destructive=True,
        ):
            return

        try:
            service.delete_member(member.id)
        except ServiceError as error:
            self.window_ref.notify_error(str(error))
            return

        self.window_ref.notify_success("Socio eliminado.")
        self.refresh()

    def _require_selection(self) -> Member | None:
        member = self.table.selected_record()
        if member is None:
            self.window_ref.notify("Selecciona un socio de la tabla primero.")
        return member
