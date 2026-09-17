"""Captura de foto del socio con la camara, en memoria hasta que se acepte."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QBuffer, QCameraPermission, QIODevice, QPermission, Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtMultimedia import (
    QCamera,
    QCameraDevice,
    QImageCapture,
    QMediaCaptureSession,
    QMediaDevices,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gym.config import APP_NAME
from gym.ui.widgets.common import primary_button, secondary_button
from gym.ui.widgets.feedback import ToastKind, ToastManager, alert

logger = logging.getLogger(__name__)

MAX_PHOTO_EDGE = 720
JPEG_QUALITY = 85
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 480
CAMERA_USAGE_DESCRIPTION = f"{APP_NAME} toma la foto del socio para identificarlo en recepción."


VIRTUAL_CAMERA_MARKERS = (
    "obs",
    "virtual",
    "camo",
    "snap camera",
    "manycam",
    "continuity",
)


def is_virtual_camera(description: str) -> bool:
    """OBS y similares no sirven para fotografiar al socio."""
    name = description.casefold()
    return any(marker in name for marker in VIRTUAL_CAMERA_MARKERS)


def choose_camera(descriptions: list[str], default: str | None) -> str | None:
    """Elige una webcam fisica; si no hay, se queda con el default de Qt."""
    if default and not is_virtual_camera(default):
        return default
    physical = [name for name in descriptions if not is_virtual_camera(name)]
    if physical:
        return physical[0]
    if default:
        return default
    return descriptions[0] if descriptions else None


def camera_device() -> QCameraDevice | None:
    """Webcam fisica. Si solo hay camaras virtuales, se usa el default de Qt."""
    devices = [device for device in QMediaDevices.videoInputs() if not device.isNull()]
    default = QMediaDevices.defaultVideoInput()
    default_name = None if default.isNull() else default.description()
    chosen = choose_camera([device.description() for device in devices], default_name)
    if chosen is None:
        return None
    for device in devices:
        if device.description() == chosen:
            return device
    return default if not default.isNull() else None


def inject_camera_usage_description() -> bool:
    """Mete la declaracion en el bundle en memoria. Sin esto Qt no pide permiso en esta sesion."""
    if sys.platform != "darwin":
        return False
    try:
        import ctypes
        import ctypes.util
        from ctypes import c_byte, c_char_p, c_void_p

        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        lib.objc_getClass.restype = c_void_p
        lib.sel_registerName.restype = c_void_p

        def sel(name: str):
            return lib.sel_registerName(name.encode())

        def send(obj, selector, *args, restype=c_void_p, argtypes=None):
            lib.objc_msgSend.restype = restype
            lib.objc_msgSend.argtypes = [c_void_p, c_void_p, *(argtypes or [])]
            return lib.objc_msgSend(obj, sel(selector), *args)

        def nsstr(text: str):
            return send(
                lib.objc_getClass(b"NSString"),
                "stringWithUTF8String:",
                text.encode(),
                argtypes=[c_char_p],
            )

        bundle = send(lib.objc_getClass(b"NSBundle"), "mainBundle")
        info = send(bundle, "infoDictionary")
        if not bundle or not info:
            return False

        key = nsstr("NSCameraUsageDescription")
        value = nsstr(CAMERA_USAGE_DESCRIPTION)
        mutable = lib.objc_getClass(b"NSMutableDictionary")
        is_mut = send(info, "isKindOfClass:", mutable, restype=c_byte, argtypes=[c_void_p])
        target = info if is_mut else send(info, "mutableCopy")
        send(target, "setObject:forKey:", value, key, argtypes=[c_void_p, c_void_p])
        if not is_mut:
            send(
                bundle,
                "setValue:forKey:",
                target,
                nsstr("infoDictionary"),
                argtypes=[c_void_p, c_void_p],
            )
        return True
    except Exception:
        logger.exception("No se pudo declarar la camara en el bundle de Python")
        return False


def encode_jpeg(image: QImage) -> bytes:
    """Reduce y comprime la captura. Los reintentos no pasan por aqui."""
    if image.isNull():
        return b""
    working = image.convertToFormat(QImage.Format.Format_RGB32)
    if working.width() > MAX_PHOTO_EDGE or working.height() > MAX_PHOTO_EDGE:
        working = working.scaled(
            MAX_PHOTO_EDGE,
            MAX_PHOTO_EDGE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not working.save(buffer, "JPEG", JPEG_QUALITY):
        return b""
    return bytes(buffer.data())


class CameraCaptureDialog(QDialog):
    """Visor en vivo, recaptura y JPEG solo al aceptar."""

    def __init__(self, parent: QWidget | None = None, *, start_camera: bool = True) -> None:
        super().__init__(parent)
        self.jpeg: bytes | None = None
        self._captured: QImage | None = None
        self._camera: QCamera | None = None
        self._session: QMediaCaptureSession | None = None
        self._capture: QImageCapture | None = None
        self._start_on_show = start_camera
        self.toasts = ToastManager(self)

        self.setWindowTitle("Tomar foto")
        self.setModal(True)
        self.setMinimumWidth(680)

        self.viewfinder = QVideoWidget(self)
        self.viewfinder.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)

        self.still = QLabel(self)
        self.still.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.still.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.still.setObjectName("kioskPhotoSlot")
        self.still.hide()

        self.capture_button = primary_button("Capturar", self._capture_photo)
        self.use_button = primary_button("Usar esta foto", self._use_photo)
        self.retake_button = secondary_button("Volver a tomar", self._retake)
        self.cancel_button = secondary_button("Cancelar", self.reject)
        self.capture_button.setEnabled(False)
        self.use_button.hide()
        self.retake_button.hide()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.retake_button)
        buttons.addWidget(self.capture_button)
        buttons.addWidget(self.use_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.viewfinder, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.still, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._start_on_show:
            self._start_on_show = False
            self._request_permission_then_start()

    def _request_permission_then_start(self) -> None:
        if sys.platform == "darwin":
            # `python -m gym` no es un .app: Qt mira Python.app. El .exe de
            # Windows no pasa por aqui.
            inject_camera_usage_description()

        app = QApplication.instance()
        if app is None:
            self._start_camera()
            return

        permission = QCameraPermission()
        if app.checkPermission(permission) == Qt.PermissionStatus.Granted:
            self._start_camera()
            return
        app.requestPermission(permission, self, self._on_permission_result)

    @Slot(QPermission)
    def _on_permission_result(self, permission: QPermission) -> None:
        if permission.status() == Qt.PermissionStatus.Granted:
            self._start_camera()
            return
        self._notify_denied()

    def _notify_denied(self) -> None:
        alert(
            self,
            "Cámara",
            "macOS bloqueó la cámara. Si aparece un aviso del sistema, elige Permitir.",
        )

    def _start_camera(self) -> None:
        device = camera_device()
        if device is None:
            self._notify_error("No se encontró una cámara. Conecta una e intenta de nuevo.")
            return

        self._session = QMediaCaptureSession(self)
        self._camera = QCamera(device, self)
        self._capture = QImageCapture(self)
        self._session.setCamera(self._camera)
        self._session.setVideoOutput(self.viewfinder)
        self._session.setImageCapture(self._capture)

        self._camera.errorOccurred.connect(self._on_camera_error)
        self._capture.readyForCaptureChanged.connect(self.capture_button.setEnabled)
        self._capture.imageCaptured.connect(self._on_image_captured)
        self._capture.errorOccurred.connect(self._on_capture_error)

        self._camera.start()
        self.capture_button.setEnabled(self._capture.isReadyForCapture())

    def _capture_photo(self) -> None:
        if self._capture is None or not self._capture.isReadyForCapture():
            return
        self.capture_button.setEnabled(False)
        self._capture.capture()

    def _on_image_captured(self, _id: int, preview: QImage) -> None:
        self._show_preview(preview)

    def _show_preview(self, image: QImage) -> None:
        """Pasa al still. Los tests lo inyectan sin encender la camara."""
        self._captured = QImage(image)
        pixmap = QPixmap.fromImage(image).scaled(
            PREVIEW_WIDTH,
            PREVIEW_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.still.setPixmap(pixmap)
        self.viewfinder.hide()
        self.still.show()
        self.capture_button.hide()
        self.use_button.show()
        self.retake_button.show()

    def _retake(self) -> None:
        self._captured = None
        self.still.clear()
        self.still.hide()
        self.viewfinder.show()
        self.use_button.hide()
        self.retake_button.hide()
        self.capture_button.show()
        ready = self._capture is not None and self._capture.isReadyForCapture()
        self.capture_button.setEnabled(ready)

    def _use_photo(self) -> None:
        if self._captured is None or self._captured.isNull():
            return
        jpeg = encode_jpeg(self._captured)
        if not jpeg:
            self._notify_error("No se pudo tomar la foto. Intenta de nuevo.")
            return
        self.jpeg = jpeg
        self.accept()

    def _on_camera_error(self, _error, message: str) -> None:
        self._notify_error(message or "No se pudo encender la cámara.")

    def _on_capture_error(self, _id: int, _error, message: str) -> None:
        ready = self._capture is not None and self._capture.isReadyForCapture()
        self.capture_button.setEnabled(ready)
        self._notify_error(message or "No se pudo tomar la foto. Intenta de nuevo.")

    def _notify_error(self, message: str) -> None:
        self.toasts.show(message, ToastKind.ERROR)

    def _release_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
        if self._session is not None:
            self._session.setVideoOutput(None)
            self._session.setImageCapture(None)
            self._session.setCamera(None)
        self._camera = None
        self._capture = None
        self._session = None

    def closeEvent(self, event) -> None:
        self._release_camera()
        super().closeEvent(event)
