"""Tipos de columna personalizados."""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import String, TypeDecorator


class EnumValue(TypeDecorator):
    """Guarda el `value` de un Enum como texto y lo reconstruye al leer.

    Se prefiere sobre `sqlalchemy.Enum` porque deja el valor legible en la base
    (util al inspeccionar respaldos con cualquier visor de SQLite) y no depende
    de como Python represente el Enum al convertirlo a cadena.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[Enum], length: int = 20) -> None:
        super().__init__(length)
        self.enum_class = enum_class

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return self.enum_class(value).value

    def process_result_value(self, value: Any, dialect: Any) -> Enum | None:
        if value is None:
            return None
        return self.enum_class(value)
