"""Avisos flotantes y dialogos de confirmacion."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMessageBox,
    QWidget,
)
from shiboken6 import isValid


class ToastKind(str, Enum):
    SUCCESS = "toastSuccess"
    ERROR = "toastError"
    INFO = "toastInfo"


class Toast(QLabel):
    """Aviso temporal en la esquina inferior de la ventana."""

    def __init__(self, parent: QWidget, message: str, kind: ToastKind, duration_ms: int) -> None:
        super().__init__(message, parent)
        self.setObjectName(kind.value)
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.adjustSize()

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)

        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        QTimer.singleShot(duration_ms, self.dismiss)

    def show_at(self, position: QPoint) -> None:
        self.move(position)
        self.show()
        self.raise_()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def dismiss(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.deleteLater)
        self._fade.start()


class ToastManager:
    """Apila los avisos para que no se encimen."""

    MARGIN = 24
    SPACING = 10

    def __init__(self, host: QWidget) -> None:
        self.host = host
        self._toasts: list[Toast] = []

    def show(self, message: str, kind: ToastKind = ToastKind.INFO, duration_ms: int = 3200) -> None:
        toast = Toast(self.host, message, kind, duration_ms)
        toast.destroyed.connect(lambda: self._forget(toast))
        self._toasts.append(toast)
        self.reposition()
        toast.show_at(toast.pos())

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self.reposition()

    def reposition(self) -> None:
        # Un aviso puede sobrevivir unos milisegundos a la ventana que lo aloja;
        # tocar el objeto C++ ya liberado terminaria la aplicacion.
        if not isValid(self.host):
            self._toasts.clear()
            return

        bottom = self.host.height() - self.MARGIN
        for toast in reversed(self._toasts):
            if not isValid(toast):
                continue
            toast.adjustSize()
            x = max(self.MARGIN, self.host.width() - toast.width() - self.MARGIN)
            top = bottom - toast.height()
            if top < self.MARGIN:
                top = self.MARGIN
            toast.move(x, top)
            bottom = top - self.SPACING


def confirm(
    parent: QWidget,
    title: str,
    message: str,
    confirm_text: str = "Confirmar",
    destructive: bool = False,
) -> bool:
    """Dialogo de si/no. Por defecto la opcion segura tiene el foco."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question)

    accept = box.addButton(confirm_text, QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    if destructive:
        accept.setObjectName("danger")

    box.exec()
    return box.clickedButton() is accept


def alert(parent: QWidget, title: str, message: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Information)
    box.exec()
