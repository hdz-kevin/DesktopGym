"""Historial de pagos de una membresia. Solo lectura: los cobros no se corrigen."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

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
        self.setObjectName("membershipHistory")
        self.membership_id = membership_id
        self.changed = False

        membership = service.get_membership(membership_id)
        self.setWindowTitle(f"Historial · {membership.member.name}")
        self.setModal(True)
        self.setMinimumSize(840, 520)

        self.payments_value = QLabel("", self)
        self.total_value = QLabel("", self)

        details = QFormLayout()
        details.setVerticalSpacing(14)
        details.setHorizontalSpacing(16)
        details.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        details.addRow(self._label("Pagos"), self.payments_value)
        details.addRow(self._label("Total pagado"), self.total_value)

        self.table = PagedTable[Payment](
            columns=[
                Column("Vigencia", lambda p: format_range(p.start_date, p.end_date), stretch=True),
                Column("Plan", lambda p: p.plan.label, width=210),
                Column(
                    "Importe",
                    lambda p: format_money(p.price_paid_cents),
                    width=110,
                ),
                Column(
                    "",
                    lambda p: "Vigente" if p.is_current else "",
                    width=90,
                    color=lambda p: SUCCESS if p.is_current else None,
                ),
            ],
            page_size=30,
            empty_text="Esta membresía no tiene pagos.",
        )
        self.table.page_changed.connect(lambda _: self.load())

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(20)
        body.addWidget(self._heading(membership))
        body.addLayout(details)
        body.addWidget(self.table, 1)

        layout.addLayout(body, 1)
        layout.addLayout(buttons)

        self.load()

    def _heading(self, membership) -> QWidget:
        box = QWidget(self)
        box.setObjectName("membershipHeading")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        title = QLabel(f"Historial de {membership.member.name}", box)
        title.setObjectName("pageTitle")
        row.addWidget(title)
        row.addWidget(status_badge(membership.status))
        row.addStretch(1)
        return box

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label

    def load(self) -> None:
        membership = service.get_membership(self.membership_id)
        payments = sorted(membership.payments, key=lambda p: p.start_date, reverse=True)
        total = len(payments)
        page = payments[self.table.offset : self.table.offset + self.table.page_size]
        self.table.set_data(page, total)
        self.payments_value.setText(str(total))
        self.total_value.setText(format_money(membership.total_paid_cents))
