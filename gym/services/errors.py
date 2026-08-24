"""Errores de negocio.

Llevan un mensaje ya redactado para el recepcionista: la interfaz solo tiene
que mostrarlo, sin traducir codigos.
"""

from __future__ import annotations


class ServiceError(Exception):
    """Operacion rechazada por una regla de negocio."""


class ValidationError(ServiceError):
    """Datos de formulario invalidos, por campo."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors.values()))


class NotFoundError(ServiceError):
    pass


class InsufficientStockError(ServiceError):
    def __init__(self, product_name: str, available: int) -> None:
        self.product_name = product_name
        self.available = available
        super().__init__(f'Stock insuficiente para "{product_name}". Quedan {available} piezas.')
