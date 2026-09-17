"""Ajustes del gimnasio y respaldos."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from gym.config import backups_dir, data_dir
from gym.domain.dates import format_datetime
from gym.services import backup as service
from gym.services.backup import BackupFile
from gym.ui.main_window import Page
from gym.ui.theme import TEXT_MUTED
from gym.ui.widgets.common import (
    Card,
    PageHeader,
    danger_button,
    primary_button,
    secondary_button,
)
from gym.ui.widgets.feedback import alert, confirm
from gym.ui.widgets.inputs import Field, MoneyInput
from gym.ui.widgets.table import Column, PagedTable

logger = logging.getLogger(__name__)


class SettingsPage(Page):
    title = "Ajustes"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self.settings = window.settings

        header = PageHeader("Ajustes", "Preferencias del gimnasio y respaldos de la información")

        self.name_input = QLineEdit(self)
        self.name_field = Field("Nombre", self.name_input, self)

        self.address_input = QLineEdit(self)
        self.address_field = Field("Dirección", self.address_input, self)

        self.visit_price_input = MoneyInput(self)
        self.visit_price_field = Field("Precio sugerido para visitas", self.visit_price_input, self)

        self.keep_input = QSpinBox(self)
        self.keep_input.setRange(1, 365)
        self.keep_field = Field("Respaldos a conservar", self.keep_input, self)

        for field in (
            self.name_field,
            self.address_field,
            self.visit_price_field,
            self.keep_field,
        ):
            field.layout().setSpacing(12)

        self.backup_on_exit = QCheckBox("Respaldar automáticamente al cerrar", self)

        self.gym_card = Card(self)
        self.gym_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.gym_card.body.setSpacing(32)
        gym_title = QLabel("Preferencias", self.gym_card)
        gym_title.setObjectName("formLabel")
        self.gym_card.body.addWidget(gym_title)
        self.gym_card.body.addWidget(self.name_field)
        self.gym_card.body.addWidget(self.address_field)
        self.gym_card.body.addWidget(self.visit_price_field)
        self.gym_card.body.addWidget(self.keep_field)
        self.gym_card.body.addWidget(self.backup_on_exit)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(primary_button("Guardar ajustes", self.save_settings))
        self.gym_card.body.addLayout(save_row)

        self.location_label = QLabel("", self)
        self.location_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 15px;")
        self.location_label.setWordWrap(True)

        self.backups_table = PagedTable[BackupFile](
            columns=[
                Column("Fecha", lambda b: format_datetime(b.created_at), stretch=True),
                Column(
                    "Tamaño",
                    lambda b: b.size_label,
                    width=100,
                    align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            ],
            empty_text="Todavía no hay respaldos.",
            paginated=False,
        )

        backup_buttons = QHBoxLayout()
        backup_buttons.setSpacing(8)
        backup_buttons.addWidget(primary_button("Respaldar ahora", self.backup_now))
        backup_buttons.addWidget(secondary_button("Restaurar seleccionado", self.restore_selected))
        backup_buttons.addWidget(secondary_button("Abrir carpeta", self.open_folder))
        backup_buttons.addStretch(1)
        backup_buttons.addWidget(
            danger_button("Restaurar desde archivo...", self.restore_from_file)
        )

        self.backup_card = Card(self)
        self.backup_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        backup_title = QLabel("Respaldos", self.backup_card)
        backup_title.setObjectName("formLabel")
        self.backup_card.body.addWidget(backup_title)
        self.backup_card.body.addWidget(self.location_label)
        self.backup_card.body.addWidget(self.backups_table, 1)
        self.backup_card.body.addLayout(backup_buttons)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self.gym_card, 2, Qt.AlignmentFlag.AlignTop)
        columns.addWidget(self.backup_card, 3)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addLayout(columns, 1)

    def refresh(self) -> None:
        self.name_input.setText(self.settings.gym_name)
        self.address_input.setText(self.settings.gym_address)
        self.visit_price_input.set_cents(self.settings.visit_price_cents)
        self.backup_on_exit.setChecked(self.settings.backup_on_exit)
        self.keep_input.setValue(self.settings.backups_to_keep)
        self.location_label.setText(f"Los datos y respaldos se guardan en: {data_dir()}")
        self.load_backups()

    def load_backups(self) -> None:
        backups = service.list_backups()
        self.backups_table.set_data(backups, len(backups))

    def save_settings(self) -> None:
        self.name_field.clear_error()
        self.visit_price_field.clear_error()

        name = self.name_input.text().strip()
        if not name:
            self.name_field.show_error("El nombre del gimnasio es obligatorio.")
            return
        if not self.visit_price_input.is_valid():
            self.visit_price_field.show_error("Escribe un importe válido, por ejemplo 40.00")
            return

        self.settings.gym_name = name
        self.settings.gym_address = self.address_input.text().strip()
        self.settings.visit_price_cents = self.visit_price_input.cents()
        self.settings.backup_on_exit = self.backup_on_exit.isChecked()
        self.settings.backups_to_keep = self.keep_input.value()

        try:
            self.settings.save()
        except OSError:
            logger.exception("No se pudieron guardar los ajustes")
            self.window_ref.notify_error("No se pudieron guardar los ajustes.")
            return

        self.window_ref.apply_settings()
        self.window_ref.notify_success("Ajustes guardados.")

    def backup_now(self) -> None:
        try:
            path = service.run_backup(self.settings)
        except Exception:
            logger.exception("Fallo el respaldo manual")
            self.window_ref.notify_error("No se pudo crear el respaldo.")
            return

        self.window_ref.notify_success(f"Respaldo creado: {path.name}")
        self.load_backups()

    def restore_selected(self) -> None:
        backup = self.backups_table.selected_record()
        if backup is None:
            self.window_ref.notify("Selecciona un respaldo de la lista primero.")
            return
        self._restore(backup.path)

    def restore_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir respaldo", str(backups_dir()), "Bases de datos (*.sqlite)"
        )
        if path:
            from pathlib import Path

            self._restore(Path(path))

    def _restore(self, path) -> None:
        if not confirm(
            self,
            "Restaurar respaldo",
            f"Se reemplazará toda la información actual con el respaldo «{path.name}».\n\n"
            "Antes de reemplazarla se guardará una copia del estado actual.",
            confirm_text="Restaurar",
            destructive=True,
        ):
            return

        try:
            service.restore_backup(path)
        except Exception as error:
            logger.exception("Fallo la restauracion")
            alert(self, "No se pudo restaurar", str(error))
            return

        alert(
            self,
            "Respaldo restaurado",
            "La información fue restaurada correctamente.\n\n"
            "Se recomienda cerrar y volver a abrir el sistema.",
        )
        self.load_backups()

    def open_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backups_dir())))
