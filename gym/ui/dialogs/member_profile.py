"""Perfil del socio: foto, datos y estado."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
from gym.ui.pages.helpers import avatar_pixmap
from gym.ui.theme import TEXT_MUTED
from gym.ui.widgets.common import Card, secondary_button, status_badge


class MemberProfileDialog(QDialog):
    def __init__(self, member: Member, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Socio · {member.name}")
        self.setModal(True)
        self.setMinimumWidth(460)

        avatar = QLabel(self)
        avatar.setFixedSize(88, 88)
        avatar.setPixmap(avatar_pixmap(member.photo, member.initials, size=88))

        name = QLabel(member.name, self)
        name_font = QFont()
        name_font.setPointSize(16)
        name_font.setBold(True)
        name.setFont(name_font)
        name.setWordWrap(True)

        code = QLabel(f"Código {member.code}", self)
        code.setStyleSheet(f"color: {TEXT_MUTED};")

        heading_text = QVBoxLayout()
        heading_text.setSpacing(4)
        heading_text.addWidget(name)
        heading_text.addWidget(code)
        heading_text.addWidget(status_badge(member.status), alignment=Qt.AlignmentFlag.AlignLeft)
        heading_text.addStretch(1)

        heading = QHBoxLayout()
        heading.setSpacing(16)
        heading.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        heading.addLayout(heading_text, 1)

        details = QFormLayout()
        details.setSpacing(8)
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
        layout.addLayout(heading)
        layout.addWidget(details_card)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(secondary_button("Cerrar", self.accept))
        layout.addLayout(close_row)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("formLabel")
        return label
