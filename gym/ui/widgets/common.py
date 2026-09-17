"""Piezas visuales pequenas compartidas entre pantallas."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gym.domain.enums import MemberStatus

BADGE_BY_STATUS = {
    MemberStatus.ACTIVE: "badgeSuccess",
    MemberStatus.EXPIRED: "badgeDanger",
}


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)


class StatCard(Card):
    """Tarjeta de metrica con valor grande y etiqueta."""

    def __init__(self, label: str, value: str = "0", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.value_label = QLabel(value, self)
        self.value_label.setObjectName("statValue")
        self.caption = QLabel(label, self)
        self.caption.setObjectName("statLabel")
        self.body.addWidget(self.value_label)
        self.body.addWidget(self.caption)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class Badge(QLabel):
    def __init__(self, text: str, object_name: str = "badgeNeutral", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName(object_name)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMaximumWidth(160)


def status_badge(status) -> Badge:
    return Badge(status.label(), BADGE_BY_STATUS.get(status, "badgeNeutral"))


class FilterChips(QWidget):
    """Grupo de botones excluyentes, como las pestanas de filtro del sistema web."""

    changed = Signal(object)

    def __init__(self, options: list[tuple[object, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values: dict[QPushButton, object] = {}

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for index, (value, label) in enumerate(options):
            button = QPushButton(label, self)
            button.setObjectName("filterChip")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setChecked(index == 0)
            self._values[button] = value
            self._group.addButton(button)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignBottom)

        layout.addStretch(1)
        self._group.buttonClicked.connect(lambda button: self.changed.emit(self._values[button]))

    def current(self) -> object:
        checked = self._group.checkedButton()
        return self._values.get(checked) if checked else None

    def set_label(self, value: object, label: str) -> None:
        for button, button_value in self._values.items():
            if button_value == value:
                button.setText(label)
                return


class ControlsRow(QHBoxLayout):
    """Busqueda, filtros y acciones alineados abajo, como align-items: end."""

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(12)

    def addWidget(self, widget, stretch: int = 0, alignment=None) -> None:
        if alignment is None:
            alignment = Qt.AlignmentFlag.AlignBottom
        super().addWidget(widget, stretch, alignment)


class PageHeader(QWidget):
    """Titulo, subtitulo y una zona de acciones a la derecha."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("pageTitle")

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(4)
        text.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setVisible(bool(subtitle))
        text.addWidget(self.subtitle_label)

        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(8)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(text)
        layout.addStretch(1)
        layout.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def add_action(self, button: QPushButton) -> None:
        self.actions.addWidget(button)


def primary_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(lambda: on_click())
    return button


def secondary_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(lambda: on_click())
    return button


def danger_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("danger")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(lambda: on_click())
    return button


def horizontal_rule() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line
