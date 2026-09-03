"""Historial de pagos de una membresia. Solo lectura: los cobros no se corrigen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.data.models import Payment
from gym.domain.dates import format_range
from gym.domain.money import format_money
from gym.services import memberships as service
from gym.ui.theme import SUCCESS
from gym.ui.widgets.common import secondary_button, status_badge
from gym.ui.widgets.table import Column, PagedTable


class MembershipHistoryDialog(QDialog):
    def __init__(self, membership_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.membership_id = membership_id
        self.changed = False

        membership = service.get_membership(membership_id)
        self.setWindowTitle(f"Historial · {membership.member.name}")
        self.setModal(True)
        self.setMinimumSize(800, 520)

        self.summary = QLabel("", self)
        self.summary.setObjectName("muted")

        self.table = PagedTable[Payment](
            columns=[
                Column("Vigencia", lambda p: format_range(p.start_date, p.end_date), stretch=True),
                Column("Plan", lambda p: p.plan.label, width=200),
                Column(
                    "Importe",
                    lambda p: format_money(p.price_paid_cents),
                    width=110,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
                Column(
                    "",
                    lambda p: "Vigente" if p.is_current else "",
                    width=90,
                    color=lambda p: SUCCESS if p.is_current else None,
                ),
            ],
            page_size=50,
            empty_text="Esta membresía no tiene pagos.",
        )

        buttons = QHBoxLayout()
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

        title = QLabel(f"Membresía de {membership.member.name}", box)
        title.setObjectName("pageTitle")
        row.addWidget(title)
        row.addWidget(status_badge(membership.status))
        row.addStretch(1)
        return box

    def load(self) -> None:
        membership = service.get_membership(self.membership_id)
        payments = sorted(membership.payments, key=lambda p: p.start_date, reverse=True)
        self.table.set_data(payments, len(payments))
        self.summary.setText(
            f"{len(payments)} pago(s) · Total pagado: {format_money(membership.total_paid_cents)}"
        )
