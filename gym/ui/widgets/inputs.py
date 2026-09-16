"""Campos de entrada compartidos."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from gym.domain.money import format_money, to_cents, to_pesos

SEARCH_DEBOUNCE_MS = 300


class SearchBox(QLineEdit):
    """Caja de busqueda que espera a que el usuario deje de teclear.

    Sin la espera, escribir "Guadalupe" lanzaria nueve consultas.
    """

    search_changed = Signal(str)

    def __init__(self, placeholder: str = "Buscar...", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchBox")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._timer.timeout.connect(lambda: self.search_changed.emit(self.text().strip()))
        self.textChanged.connect(lambda _: self._timer.start())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        from PySide6.QtCore import Qt

        if event.key() == Qt.Key.Key_Escape and self.text():
            self.clear()
            self._timer.stop()
            self.search_changed.emit("")
            return
        super().keyPressEvent(event)


class MoneyInput(QLineEdit):
    """Campo de importe que trabaja internamente en centavos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.editingFinished.connect(self._normalize)

    def set_cents(self, cents: int | None) -> None:
        self.setText("" if cents is None else f"{to_pesos(cents):.2f}")

    def cents(self) -> int:
        text = self.text().strip()
        if not text:
            return 0
        return to_cents(text)

    def is_valid(self) -> bool:
        text = self.text().strip()
        if not text:
            return False
        try:
            return to_cents(text) >= 0
        except ValueError:
            return False

    def _normalize(self) -> None:
        if self.is_valid():
            self.set_cents(self.cents())


class Field(QWidget):
    """Etiqueta, control y espacio para el mensaje de error."""

    def __init__(self, label: str, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.widget = widget

        self.label = QLabel(label, self)
        self.label.setObjectName("formLabel")

        self.error = QLabel("", self)
        self.error.setObjectName("errorText")
        self.error.setWordWrap(True)
        self.error.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.label)
        layout.addWidget(widget)
        layout.addWidget(self.error)

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()
        self.widget.setProperty("invalid", "true")
        self._repolish()

    def clear_error(self) -> None:
        self.error.clear()
        self.error.hide()
        self.widget.setProperty("invalid", "false")
        self._repolish()

    def _repolish(self) -> None:
        style = self.widget.style()
        style.unpolish(self.widget)
        style.polish(self.widget)


def money_label(cents: int) -> QLabel:
    label = QLabel(format_money(cents))
    label.setObjectName("statValue")
    return label
