"""Arranque de la aplicacion."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from gym.config import Settings
from gym.data.database import init_engine
from gym.data.schema import prepare_database
from gym.logging_setup import configure_logging, install_exception_hook
from gym.single_instance import InstanceLock
from gym.ui.theme import apply_appearance

logger = logging.getLogger(__name__)


def build_window(settings: Settings):
    """Construye la ventana con todas sus paginas registradas."""
    from gym.ui.main_window import MainWindow
    from gym.ui.pages.cash import CashPage
    from gym.ui.pages.kiosk import KioskPage
    from gym.ui.pages.members import MembersPage
    from gym.ui.pages.memberships import MembershipsPage
    from gym.ui.pages.plans import PlansPage
    from gym.ui.pages.products import ProductsPage
    from gym.ui.pages.sales import SalesPage
    from gym.ui.pages.settings import SettingsPage
    from gym.ui.pages.visits import VisitsPage

    window = MainWindow(settings)
    window.register_page("kiosk", KioskPage(window))
    window.register_page("members", MembersPage(window))
    window.register_page("memberships", MembershipsPage(window))
    window.register_page("visits", VisitsPage(window))
    window.register_page("plans", PlansPage(window))
    window.register_page("cash", CashPage(window))
    window.register_page("products", ProductsPage(window))
    window.register_page("sales", SalesPage(window))
    window.register_page("settings", SettingsPage(window))
    window.show_page("kiosk")
    return window


def main() -> int:
    configure_logging()
    install_exception_hook()

    app = QApplication(sys.argv)
    app.setApplicationName("TecnoGym")
    apply_appearance(app)

    lock = InstanceLock()
    if not lock.acquire():
        QMessageBox.warning(
            None,
            "TecnoGym",
            "El sistema ya está abierto en otra ventana.\n\n"
            "Busca la ventana existente en la barra de tareas.",
        )
        return 0

    try:
        init_engine()
        prepare_database()
    except Exception:
        logger.exception("No se pudo preparar la base de datos")
        QMessageBox.critical(
            None,
            "TecnoGym",
            "No se pudo abrir la base de datos.\n\n"
            "Revisa el archivo de registro o restaura un respaldo reciente.",
        )
        lock.release()
        return 1

    settings = Settings.load()
    window = build_window(settings)
    window.show()

    try:
        return app.exec()
    finally:
        from gym.services.backup import run_exit_backup

        try:
            run_exit_backup(settings)
        except Exception:
            logger.exception("Fallo el respaldo de cierre")
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
