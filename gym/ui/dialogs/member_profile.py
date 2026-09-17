"""Perfil del socio: foto, datos e historial de pagos."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.data.models import Member, Payment
from gym.domain.dates import format_range, humanize_delta
from gym.domain.enums import MemberStatus
from gym.domain.money import format_money
from gym.services import members as service
from gym.ui.pages.helpers import slot_pixmap
from gym.ui.theme import SUCCESS
from gym.ui.widgets.common import secondary_button, status_badge
from gym.ui.widgets.table import Column, PagedTable

PHOTO_SIZE = 220


def _vigencia_text(member: Member) -> str:
    payment = member.recent_payment
    if payment is None:
        return "—"
    delta = humanize_delta(payment.end_date)
    if member.status is MemberStatus.ACTIVE:
        return f"Vence en {delta}"
    return f"Venció hace {delta}"


class MemberProfileDialog(QDialog):
    def __init__(self, member: Member, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("memberProfile")
        self.member_id = member.id
        self.setWindowTitle(f"Socio · {member.name}")
        self.setModal(True)
        self.setMinimumSize(840, 640)

        self.payments_value = QLabel("", self)
        self.total_value = QLabel("", self)
        self.vigencia_value = QLabel(_vigencia_text(member), self)

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
            empty_text="Este socio no tiene pagos.",
        )
        self.table.page_changed.connect(lambda _: self.load())

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cerrar", self.accept))

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self._heading(member))
        layout.addSpacing(14)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

        self.load()

    def _heading(self, member: Member) -> QWidget:
        box = QWidget(self)
        box.setObjectName("memberHeading")
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(18)

        avatar = QLabel(box)
        avatar.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
        avatar.setPixmap(slot_pixmap(member.photo, member.initials, size=PHOTO_SIZE))

        name = QLabel(member.name, box)
        name.setObjectName("memberName")
        name.setWordWrap(True)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(12)
        name_row.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addWidget(status_badge(member.status), 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addStretch(1)

        details = QFormLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setVerticalSpacing(14)
        details.setHorizontalSpacing(16)
        details.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        details.addRow(self._label("Código"), QLabel(member.code, self))
        details.addRow(self._label("Categoría"), QLabel(member.plan_category.name, self))
        details.addRow(self._label("Vigencia"), self.vigencia_value)
        details.addRow(self._label("Pagos"), self.payments_value)
        details.addRow(self._label("Total pagado"), self.total_value)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(12)
        text.addLayout(name_row)
        text.addLayout(details)
        text.addStretch(1)

        row.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        row.addLayout(text, 1)
        return box

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label

    def load(self) -> None:
        member = service.get_member(self.member_id)
        payments = sorted(member.payments, key=lambda p: p.start_date, reverse=True)
        total = len(payments)
        page = payments[self.table.offset : self.table.offset + self.table.page_size]
        self.table.set_data(page, total)
        self.vigencia_value.setText(_vigencia_text(member))
        self.payments_value.setText(str(total))
        self.total_value.setText(format_money(member.total_paid_cents))
