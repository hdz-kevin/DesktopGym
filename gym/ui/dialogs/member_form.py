"""Alta y edicion de socios."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Member
from gym.domain.enums import MemberGender
from gym.services import members as service
from gym.services.errors import ValidationError
from gym.ui.pages.helpers import avatar_pixmap
from gym.ui.widgets.common import primary_button, secondary_button
from gym.ui.widgets.inputs import Field


class MemberFormDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, member: Member | None = None) -> None:
        super().__init__(parent)
        self.member = member
        self.member_id: int | None = member.id if member else None
        self._photo_source: Path | None = None
        self._remove_photo = False

        self.setWindowTitle("Editar socio" if member else "Nuevo socio")
        self.setModal(True)
        self.setMinimumWidth(460)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Nombre completo")
        self.name_field = Field("Nombre", self.name_input, self)

        self.gender_input = QComboBox(self)
        for gender in MemberGender:
            self.gender_input.addItem(gender.label(), gender)
        self.gender_field = Field("Género", self.gender_input, self)

        self.birth_input = QDateEdit(self)
        self.birth_input.setCalendarPopup(True)
        self.birth_input.setDisplayFormat("dd/MM/yyyy")
        self.birth_input.setMaximumDate(QDate.currentDate())
        self.birth_input.setDate(QDate(2000, 1, 1))
        self.birth_input.setEnabled(False)

        self.has_birth = QCheckBox("Registrar fecha de nacimiento", self)
        self.has_birth.toggled.connect(self.birth_input.setEnabled)

        birth_box = QWidget(self)
        birth_layout = QVBoxLayout(birth_box)
        birth_layout.setContentsMargins(0, 0, 0, 0)
        birth_layout.setSpacing(6)
        birth_layout.addWidget(self.has_birth)
        birth_layout.addWidget(self.birth_input)
        self.birth_field = Field("Fecha de nacimiento", birth_box, self)

        self.avatar = QLabel(self)
        self.avatar.setFixedSize(72, 72)
        self.choose_photo = secondary_button("Elegir foto...", self._pick_photo)
        self.clear_photo = secondary_button("Quitar", self._clear_photo)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(10)
        photo_row.addWidget(self.avatar)
        photo_row.addWidget(self.choose_photo)
        photo_row.addWidget(self.clear_photo)
        photo_row.addStretch(1)

        photo_box = QWidget(self)
        photo_box.setLayout(photo_row)
        self.photo_field = Field("Foto", photo_box, self)

        self.save_button = primary_button("Guardar", self.accept)
        self.save_button.setDefault(True)
        cancel_button = secondary_button("Cancelar", self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.name_field)
        layout.addWidget(self.gender_field)
        layout.addWidget(self.birth_field)
        layout.addWidget(self.photo_field)
        layout.addSpacing(6)
        layout.addLayout(buttons)

        if member:
            self._load(member)
        self._render_avatar()
        self.name_input.setFocus()

    def _load(self, member: Member) -> None:
        self.name_input.setText(member.name)
        index = self.gender_input.findData(member.gender)
        if index >= 0:
            self.gender_input.setCurrentIndex(index)
        if member.birth_date:
            self.has_birth.setChecked(True)
            self.birth_input.setDate(
                QDate(member.birth_date.year, member.birth_date.month, member.birth_date.day)
            )

    def _render_avatar(self) -> None:
        if self._photo_source is not None:
            from PySide6.QtGui import QPixmap

            pixmap = QPixmap(str(self._photo_source)).scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.avatar.setPixmap(pixmap)
            return

        photo = None if self._remove_photo else (self.member.photo if self.member else None)
        initials = self.name_input.text().strip()[:2].upper() or "?"
        self.avatar.setPixmap(avatar_pixmap(photo, initials, size=72))

    def _pick_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir foto", "", "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if path:
            self._photo_source = Path(path)
            self._remove_photo = False
            self._render_avatar()

    def _clear_photo(self) -> None:
        self._photo_source = None
        self._remove_photo = True
        self._render_avatar()

    def build_form(self) -> service.MemberForm:
        birth: date | None = None
        if self.has_birth.isChecked():
            qdate = self.birth_input.date()
            birth = date(qdate.year(), qdate.month(), qdate.day())

        return service.MemberForm(
            name=self.name_input.text(),
            # Qt devuelve el dato del combo como texto plano, no como Enum.
            gender=MemberGender(self.gender_input.currentData()),
            birth_date=birth,
            photo_source=self._photo_source,
            remove_photo=self._remove_photo,
        )

    def accept(self) -> None:
        for field in (self.name_field, self.birth_field, self.photo_field):
            field.clear_error()

        form = self.build_form()
        try:
            if self.member_id is None:
                self.member_id = service.create_member(form)
            else:
                service.update_member(self.member_id, form)
        except ValidationError as error:
            self._show_errors(error.errors)
            return
        super().accept()

    def _show_errors(self, errors: dict[str, str]) -> None:
        mapping = {
            "name": self.name_field,
            "birth_date": self.birth_field,
            "photo": self.photo_field,
        }
        for key, message in errors.items():
            field = mapping.get(key)
            if field:
                field.show_error(message)
