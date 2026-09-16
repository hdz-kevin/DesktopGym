"""Pantalla de bienvenida: el socio teclea su codigo y sabe si puede pasar.

Es la pantalla de mayor uso diario, asi que funciona entera con el teclado y el
campo recupera el foco solo. Un lector de codigos de barras se comporta como un
teclado que termina con Enter, de modo que ya queda soportado.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QEvent, QRegularExpression, Qt, QTimer
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gym.config import Settings
from gym.domain.dates import format_date
from gym.services.checkin import CODE_LENGTH, CheckInResult, verify_code
from gym.ui.main_window import Page
from gym.ui.pages.helpers import slot_pixmap
from gym.ui.theme import DANGER, SUCCESS, TEXT, TEXT_MUTED

logger = logging.getLogger(__name__)

RESULT_HOLD_MS = 1000 * 10
PILL_WIDTH = 400
PILL_HEIGHT = 64
PHOTO_SIZE = 400
CENTER_WIDTH = 780
_WEEKDAYS = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


def _clock_parts(moment: datetime) -> tuple[str, str]:
    hour = moment.hour % 12 or 12
    meridiem = "a.m." if moment.hour < 12 else "p.m."
    time_text = f"{hour}:{moment.minute:02d} {meridiem}"
    date_text = f"{_WEEKDAYS[moment.weekday()]} {format_date(moment)}"
    return time_text, date_text


class CodeInput(QLineEdit):
    """Capsula visible del codigo. Un lector de barras escribe aqui como teclado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("kioskCodeInput")
        self.setMaxLength(CODE_LENGTH)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,5}")))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(PILL_WIDTH, PILL_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


class KioskPage(Page):
    title = "Bienvenida"

    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ref = window
        self.settings: Settings = window.settings
        self._showing_result = False

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self.reset)

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick)

        self.heading = QLabel("", self)
        self.heading.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {TEXT};")
        self.heading.setContentsMargins(0, 0, 0, 5)
        self.heading.setWordWrap(True)

        self.address = QLabel("", self)
        self.address.setStyleSheet(f"font-size: 16px; color: {TEXT_MUTED};")
        self.address.setWordWrap(True)

        gym = QWidget(self)
        gym_layout = QVBoxLayout(gym)
        gym_layout.setContentsMargins(0, 0, 0, 0)
        gym_layout.setSpacing(2)
        gym_layout.addWidget(self.heading)
        gym_layout.addWidget(self.address)

        self.clock_time = QLabel(self)
        self.clock_time.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {TEXT};")
        self.clock_time.setObjectName("kioskClock")
        self.clock_time.setContentsMargins(0, 0, 0, 5)
        self.clock_time.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.clock_date = QLabel(self)
        self.clock_date.setStyleSheet(f"font-size: 16px; color: {TEXT_MUTED};")
        self.clock_date.setObjectName("kioskDate")
        self.clock_date.setAlignment(Qt.AlignmentFlag.AlignRight)

        clock = QWidget(self)
        clock_layout = QVBoxLayout(clock)
        clock_layout.setContentsMargins(0, 0, 0, 0)
        clock_layout.setSpacing(2)
        clock_layout.addWidget(self.clock_time)
        clock_layout.addWidget(self.clock_date)

        top = QHBoxLayout()
        top.addWidget(gym, 1, Qt.AlignmentFlag.AlignTop)
        top.addWidget(clock, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.instruction = QLabel("Ingresa tu código de 5 dígitos", self)
        self.instruction.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {TEXT};")
        self.instruction.setContentsMargins(0, 0, 0, 8)
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.code_input = CodeInput(self)
        self.code_input.returnPressed.connect(self.check)
        self.code_input.textChanged.connect(self._on_text_changed)
        self.input_card = self.code_input

        pill_row = QHBoxLayout()
        pill_row.addStretch(1)
        pill_row.addWidget(self.code_input)
        pill_row.addStretch(1)

        self.photo_slot = QLabel(self)
        self.photo_slot.setObjectName("kioskPhotoSlot")
        self.photo_slot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.photo_slot.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
        self.photo_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.result_name = QLabel("", self)
        self.result_name.setWordWrap(True)

        self.result_code_row = QWidget(self)
        code_row = QHBoxLayout(self.result_code_row)
        code_row.setContentsMargins(0, 0, 0, 0)
        code_row.setSpacing(6)
        self.result_code_label = QLabel("Código:", self.result_code_row)
        self.result_code_label.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 400;")
        self.result_code = QLabel("", self.result_code_row)
        self.result_code.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 500;")
        code_row.addWidget(self.result_code_label)
        code_row.addWidget(self.result_code)
        code_row.addStretch(1)

        self.result_detail = QLabel("", self)
        self.result_detail.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 500;")
        self.result_detail.setWordWrap(True)

        info = QVBoxLayout()
        info.setSpacing(36)
        info.addStretch(1)
        info.addWidget(self.result_name)
        info.addWidget(self.result_code_row)
        info.addWidget(self.result_detail)
        info.addStretch(1)

        self.result_block = QWidget(self)
        self.result_block.setFixedHeight(PHOTO_SIZE)
        result_row = QHBoxLayout(self.result_block)
        result_row.setContentsMargins(0, 0, 0, 0)
        result_row.setSpacing(36)
        result_row.addWidget(self.photo_slot, 0, Qt.AlignmentFlag.AlignVCenter)
        result_row.addLayout(info, 1)

        center = QWidget(self)
        center.setFixedWidth(CENTER_WIDTH)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)
        center_layout.addWidget(self.instruction)
        center_layout.addLayout(pill_row)
        center_layout.addSpacing(40)
        center_layout.addWidget(self.result_block)

        input_row = QHBoxLayout()
        input_row.addStretch(1)
        input_row.addWidget(center)
        input_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addLayout(top)
        layout.addStretch(1)
        layout.addLayout(input_row)
        layout.addStretch(2)

        self._tick()
        self._clock_timer.start()
        self._apply_gym_copy()
        self._hide_result()
        self.installEventFilter(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def refresh(self) -> None:
        self._apply_gym_copy()
        self._tick()
        self.reset()

    def reset(self) -> None:
        self._hide_result()
        self._clear_code()
        self.code_input.setEnabled(True)
        self.code_input.setFocus()

    def _apply_gym_copy(self) -> None:
        self.heading.setText(self.settings.gym_name)
        address = self.settings.gym_address.strip()
        self.address.setText(address)
        self.address.setVisible(bool(address))

    def _tick(self) -> None:
        time_text, date_text = _clock_parts(datetime.now())
        self.clock_time.setText(time_text)
        self.clock_date.setText(date_text)

    def _clear_code(self) -> None:
        self.code_input.blockSignals(True)
        self.code_input.clear()
        self.code_input.blockSignals(False)

    def _apply_accent(self, color: str) -> None:
        self.result_name.setStyleSheet(f"color: {color}; font-size: 30px; font-weight: 700;")

    def _on_text_changed(self, text: str) -> None:
        """Consulta sola al completar los cinco digitos, sin exigir Enter."""
        digits = "".join(character for character in text if character.isdigit())[:CODE_LENGTH]
        if digits != text:
            self.code_input.blockSignals(True)
            self.code_input.setText(digits)
            self.code_input.blockSignals(False)
        if not digits:
            return
        if self._showing_result:
            self._hide_result()
        if len(digits) == CODE_LENGTH:
            self.check()

    def _hide_result(self) -> None:
        self._showing_result = False
        self._reset_timer.stop()
        self.result_name.clear()
        self.result_code.clear()
        self.result_detail.clear()
        self.result_name.hide()
        self.result_code_row.hide()
        self.result_detail.hide()
        self.photo_slot.clear()
        self.photo_slot.hide()
        self._apply_accent(TEXT)

    def check(self) -> None:
        code = self.code_input.text().strip()
        if not code:
            return

        try:
            result = verify_code(code)
        except Exception:
            logger.exception("Fallo la verificacion del codigo %s", code)
            self.window_ref.notify_error("No se pudo consultar el código. Intenta de nuevo.")
            self.reset()
            return

        self._render(result)

    def _render(self, result: CheckInResult) -> None:
        accent = SUCCESS if result.granted else DANGER
        self._apply_accent(accent)

        self.photo_slot.show()

        if result.member is None:
            self.photo_slot.clear()
            self.result_name.setText(result.message)
            self.result_name.show()
            self.result_code_row.hide()
            self.result_detail.hide()
        else:
            self.photo_slot.setPixmap(
                slot_pixmap(result.member.photo, result.member.initials, size=PHOTO_SIZE)
            )
            self.result_name.setText(result.member_name)
            self.result_name.setVisible(bool(result.member_name))
            self.result_code.setText(result.member.code)
            self.result_code_row.setVisible(bool(result.member.code))
            self.result_detail.setText(result.detail)
            self.result_detail.setVisible(bool(result.detail))

        self._showing_result = True

        # Vaciar el campo dispara textChanged; sin silenciarlo, el resultado
        # que acabamos de mostrar se ocultaria en el mismo instante.
        self._clear_code()
        self.code_input.setFocus()
        self._reset_timer.start(RESULT_HOLD_MS)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.code_input.setFocus()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        self.code_input.setFocus()
        super().mousePressEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.code_input.setFocus()
