"""Alta y edicion de socios."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gym.data.models import Member
from gym.services import members as service
from gym.services import plans as plans_service
from gym.services.errors import ValidationError
from gym.ui.dialogs.camera_capture import CameraCaptureDialog, camera_device
from gym.ui.pages.helpers import avatar_pixmap
from gym.ui.widgets.common import primary_button, secondary_button
from gym.ui.widgets.feedback import ToastKind, ToastManager
from gym.ui.widgets.inputs import Field


class MemberFormDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, member: Member | None = None) -> None:
        super().__init__(parent)
        self.member = member
        self.member_id: int | None = member.id if member else None
        self._photo_jpeg: bytes | None = None
        self._remove_photo = False
        self.toasts = ToastManager(self)

        self.setWindowTitle("Editar socio" if member else "Nuevo socio")
        self.setModal(True)
        self.setMinimumWidth(460)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Nombre completo")
        self.name_field = Field("Nombre", self.name_input, self)

        self.category_input = QComboBox(self)
        for category in plans_service.list_plan_categories():
            self.category_input.addItem(category.name, category.id)
        self.category_field = Field("Categoría", self.category_input, self)

        self.avatar = QLabel(self)
        self.avatar.setFixedSize(72, 72)
        self.take_photo = secondary_button("Tomar foto", self._take_photo)
        self.clear_photo = secondary_button("Quitar", self._clear_photo)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(10)
        photo_row.addWidget(self.avatar)
        photo_row.addWidget(self.take_photo)
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
        layout.addWidget(self.category_field)
        layout.addWidget(self.photo_field)
        layout.addSpacing(6)
        layout.addLayout(buttons)

        if member:
            self._load(member)
        self._render_avatar()
        self.name_input.setFocus()

    def _load(self, member: Member) -> None:
        self.name_input.setText(member.name)
        category_index = self.category_input.findData(member.plan_category_id)
        if category_index >= 0:
            self.category_input.setCurrentIndex(category_index)

    def _render_avatar(self) -> None:
        if self._photo_jpeg is not None:
            pixmap = QPixmap()
            pixmap.loadFromData(self._photo_jpeg)
            self.avatar.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            return

        photo = None if self._remove_photo else (self.member.photo if self.member else None)
        initials = self.name_input.text().strip()[:2].upper() or "?"
        self.avatar.setPixmap(avatar_pixmap(photo, initials, size=72))

    def _take_photo(self) -> None:
        if camera_device() is None:
            self.toasts.show(
                "No se encontró una cámara. Conecta una e intenta de nuevo.",
                ToastKind.ERROR,
            )
            return

        dialog = CameraCaptureDialog(self)
        if dialog.exec() and dialog.jpeg:
            self._photo_jpeg = dialog.jpeg
            self._remove_photo = False
            self._render_avatar()

    def _clear_photo(self) -> None:
        self._photo_jpeg = None
        self._remove_photo = True
        self._render_avatar()

    def build_form(self) -> service.MemberForm:
        return service.MemberForm(
            name=self.name_input.text(),
            plan_category_id=self.category_input.currentData() or 0,
            photo_jpeg=self._photo_jpeg,
            remove_photo=self._remove_photo,
        )

    def accept(self) -> None:
        for field in (self.name_field, self.category_field, self.photo_field):
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
            "plan_category": self.category_field,
            "photo": self.photo_field,
        }
        for key, message in errors.items():
            field = mapping.get(key)
            if field:
                field.show_error(message)
