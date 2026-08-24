"""Ventana principal: barra lateral, paginas y atajos globales."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gym.config import Settings
from gym.ui.widgets.feedback import ToastKind, ToastManager

logger = logging.getLogger(__name__)

BACKUP_INTERVAL_MS = 24 * 60 * 60 * 1000


@dataclass
class NavItem:
    key: str
    label: str
    shortcut: str
    section: str


NAV_ITEMS = [
    NavItem("kiosk", "Bienvenida", "F1", "Gimnasio"),
    NavItem("members", "Socios", "F2", "Gimnasio"),
    NavItem("memberships", "Membresías", "F3", "Gimnasio"),
    NavItem("visits", "Visitas", "F4", "Gimnasio"),
    NavItem("prices", "Precios", "F5", "Gimnasio"),
    NavItem("cash", "Corte de caja", "F6", "Gimnasio"),
    NavItem("products", "Productos", "F7", "Tienda"),
    NavItem("sales", "Ventas", "F8", "Tienda"),
    NavItem("settings", "Ajustes", "F9", "Sistema"),
]


class Page(QWidget):
    """Base de las pantallas.

    `refresh` se invoca cada vez que la pagina se muestra, para que los datos
    no queden viejos al volver de otro modulo.
    """

    title = ""
    subtitle = ""

    def refresh(self) -> None:  # pragma: no cover - las subclases deciden
        pass


class Sidebar(QWidget):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(224)

        self.buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(2)

        self.title = QLabel(self)
        self.title.setObjectName("sidebarTitle")
        self.title.setWordWrap(True)
        self.title.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(self.title)

        self.address = QLabel(self)
        self.address.setObjectName("sidebarSubtitle")
        self.address.setWordWrap(True)
        self.address.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(self.address)

        self.set_gym(settings.gym_name, settings.gym_address)
        layout.addSpacing(10)

        current_section = ""
        for item in NAV_ITEMS:
            if item.section != current_section:
                current_section = item.section
                header = QLabel(item.section.upper(), self)
                header.setObjectName("sidebarSection")
                layout.addWidget(header)

            button = QPushButton(f"{item.label}", self)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"{item.label}  ({item.shortcut})")
            self.buttons[item.key] = button
            self._group.addButton(button)
            layout.addWidget(button)

        layout.addStretch(1)

        hint = QLabel("F1-F9 para navegar", self)
        hint.setObjectName("navShortcut")
        hint.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(hint)

    def set_gym(self, name: str, address: str) -> None:
        self.title.setText(name)
        self.address.setText(address)
        self.address.setVisible(bool(address))

    def mark_active(self, key: str) -> None:
        button = self.buttons.get(key)
        if button:
            button.setChecked(True)


class MainWindow(QWidget):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle(f"{settings.gym_name} - Sistema de Gimnasio")
        self.resize(1240, 780)
        self.setMinimumSize(1040, 660)

        self.pages: dict[str, Page] = {}
        self.stack = QStackedWidget(self)
        self.sidebar = Sidebar(settings, self)
        self.toasts = ToastManager(self)

        content = QWidget(self)
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 22, 24, 22)
        content_layout.addWidget(self.stack)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content, 1)

        for item in NAV_ITEMS:
            self.sidebar.buttons[item.key].clicked.connect(
                lambda _=False, key=item.key: self.show_page(key)
            )
            shortcut = QShortcut(QKeySequence(item.shortcut), self)
            shortcut.activated.connect(lambda key=item.key: self.show_page(key))

        refresh = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh.activated.connect(self.refresh_current)

        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(BACKUP_INTERVAL_MS)
        self._backup_timer.timeout.connect(self._scheduled_backup)
        self._backup_timer.start()

    def apply_settings(self) -> None:
        """Refleja en la ventana los ajustes que el usuario acaba de guardar."""
        self.setWindowTitle(f"{self.settings.gym_name} - Sistema de Gimnasio")
        self.sidebar.set_gym(self.settings.gym_name, self.settings.gym_address)
        self.refresh_current()

    def _scheduled_backup(self) -> None:
        """Respaldo periodico mientras la aplicacion esta abierta.

        En recepcion la aplicacion suele quedarse dias sin cerrarse, de modo que
        confiar solo en el respaldo de salida dejaria huecos muy largos.
        """
        from gym.services.backup import run_backup

        try:
            run_backup(self.settings)
        except Exception:
            logger.exception("Fallo el respaldo programado")

    def register_page(self, key: str, page: Page) -> None:
        self.pages[key] = page
        self.stack.addWidget(page)

    def show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            self.notify(f"El módulo «{key}» aún no está disponible.", ToastKind.INFO)
            return

        self.stack.setCurrentWidget(page)
        self.sidebar.mark_active(key)
        try:
            page.refresh()
        except Exception:
            logger.exception("Fallo al actualizar la pagina %s", key)
            self.notify("No se pudieron cargar los datos de esta pantalla.", ToastKind.ERROR)

    def refresh_current(self) -> None:
        page = self.stack.currentWidget()
        if isinstance(page, Page):
            page.refresh()

    def notify(self, message: str, kind: ToastKind = ToastKind.INFO) -> None:
        self.toasts.show(message, kind)

    def notify_success(self, message: str) -> None:
        self.notify(message, ToastKind.SUCCESS)

    def notify_error(self, message: str) -> None:
        self.notify(message, ToastKind.ERROR)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.toasts.reposition()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
