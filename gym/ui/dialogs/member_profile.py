"""Perfil del socio: foto, datos y estado."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Member
from gym.domain.dates import format_date
from gym.ui.pages.helpers import slot_pixmap
from gym.ui.widgets.common import Card, secondary_button, status_badge

PHOTO_SIZE = 200


class MemberProfileDialog(QDialog):
    def __init__(self, member: Member, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("memberProfile")
        self.setWindowTitle(f"Socio · {member.name}")
        self.setModal(True)
        self.setMinimumWidth(600)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(secondary_button("Cerrar", self.accept))

        details = QFormLayout()
        details.setVerticalSpacing(14)
        details.setHorizontalSpacing(16)
        details.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        details.addRow(self._label("Género"), QLabel(member.gender.label(), self))
        details.addRow(
            self._label("Edad"),
            QLabel(f"{member.age} años" if member.age is not None else "No registrada", self),
        )
        details.addRow(
            self._label("Nacimiento"),
            QLabel(format_date(member.birth_date) if member.birth_date else "No registrada", self),
        )
        details.addRow(self._label("Socio desde"), QLabel(format_date(member.created_at), self))

        details_card = Card(self)
        details_card.body.addLayout(details)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(20)
        body.addWidget(self._heading(member))
        body.addWidget(details_card)

        layout.addLayout(body, 1)
        layout.addLayout(buttons)

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

        code = QLabel(f"Código {member.code}", box)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(14)
        text.addWidget(name)
        text.addWidget(code)
        text.addWidget(status_badge(member.status), alignment=Qt.AlignmentFlag.AlignLeft)

        row.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(text, 1)
        row.setAlignment(text, Qt.AlignmentFlag.AlignVCenter)
        return box

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label
