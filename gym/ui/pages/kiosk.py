"""Pantalla de bienvenida: el socio teclea su codigo y sabe si puede pasar.

Es la pantalla de mayor uso diario, asi que funciona entera con el teclado y el
campo recupera el foco solo. Un lector de codigos de barras se comporta como un
teclado que termina con Enter, de modo que ya queda soportado.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gym.config import Settings
from gym.services.checkin import CODE_LENGTH, CheckInResult, verify_code
from gym.ui.main_window import Page
from gym.ui.pages.helpers import avatar_pixmap
from gym.ui.theme import DANGER, SUCCESS, TEXT_MUTED
from gym.ui.widgets.common import Card

logger = logging.getLogger(__name__)

RESULT_HOLD_MS = 6000


class CodeInput(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaxLength(CODE_LENGTH)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPlaceholderText("• • • • •")
        self.setFixedSize(280, 76)

        font = QFont()
        font.setPointSize(30)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 10)
        self.setFont(font)


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

        self.heading = QLabel(self.settings.gym_name, self)
        self.heading.setObjectName("pageTitle")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.instruction = QLabel("Ingresa tu código de socio", self)
        self.instruction.setObjectName("pageSubtitle")
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.code_input = CodeInput(self)
        self.code_input.returnPressed.connect(self.check)
        self.code_input.textChanged.connect(self._on_text_changed)

        self.result_card = Card(self)
        self.result_card.setVisible(False)
        self.result_card.setMinimumWidth(460)

        self.avatar = QLabel(self.result_card)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(96, 96)

        self.result_title = QLabel("", self.result_card)
        self.result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        result_font = QFont()
        result_font.setPointSize(19)
        result_font.setBold(True)
        self.result_title.setFont(result_font)

        self.result_name = QLabel("", self.result_card)
        self.result_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(15)
        self.result_name.setFont(name_font)

        self.result_detail = QLabel("", self.result_card)
        self.result_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_detail.setStyleSheet(f"color: {TEXT_MUTED};")
        self.result_detail.setWordWrap(True)

        avatar_row = QHBoxLayout()
        avatar_row.addStretch(1)
        avatar_row.addWidget(self.avatar)
        avatar_row.addStretch(1)

        self.result_card.body.addLayout(avatar_row)
        self.result_card.body.addWidget(self.result_title)
        self.result_card.body.addWidget(self.result_name)
        self.result_card.body.addWidget(self.result_detail)

        self.hint = QLabel("Presiona Enter para consultar", self)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

        input_row = QHBoxLayout()
        input_row.addStretch(1)
        input_row.addWidget(self.code_input)
        input_row.addStretch(1)

        card_row = QHBoxLayout()
        card_row.addStretch(1)
        card_row.addWidget(self.result_card)
        card_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addStretch(2)
        layout.addWidget(self.heading)
        layout.addWidget(self.instruction)
        layout.addSpacing(10)
        layout.addLayout(input_row)
        layout.addWidget(self.hint)
        layout.addSpacing(6)
        layout.addLayout(card_row)
        layout.addStretch(3)

    def refresh(self) -> None:
        self.heading.setText(self.settings.gym_name)
        self.reset()

    def reset(self) -> None:
        self._hide_result()
        self.code_input.blockSignals(True)
        self.code_input.clear()
        self.code_input.blockSignals(False)
        self.code_input.setEnabled(True)
        self.code_input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        """Consulta sola al completar los cinco digitos, sin exigir Enter."""
        if not text:
            return
        if self._showing_result:
            self._hide_result()
        if len(text) == CODE_LENGTH and text.isdigit():
            self.check()

    def _hide_result(self) -> None:
        self._showing_result = False
        self._reset_timer.stop()
        self.result_card.setVisible(False)

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
        color = SUCCESS if result.granted else DANGER
        self.result_title.setText(result.message)
        self.result_title.setStyleSheet(f"color: {color};")
        self.result_name.setText(result.member_name)
        self.result_name.setVisible(bool(result.member_name))
        self.result_detail.setText(result.detail)
        self.result_detail.setVisible(bool(result.detail))

        member = result.member
        self.avatar.setPixmap(
            avatar_pixmap(
                member.photo if member else None,
                member.initials if member else "?",
                size=96,
            )
        )

        self.result_card.setVisible(True)
        self._showing_result = True

        # Vaciar el campo dispara textChanged; sin silenciarlo, el resultado
        # que acabamos de mostrar se ocultaria en el mismo instante.
        self.code_input.blockSignals(True)
        self.code_input.clear()
        self.code_input.blockSignals(False)

        self.code_input.setFocus()
        self._reset_timer.start(RESULT_HOLD_MS)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.code_input.setFocus()
