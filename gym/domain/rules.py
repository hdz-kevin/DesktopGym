"""Reglas de negocio del gimnasio, independientes de la persistencia."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from gym.domain.dates import add_months, end_of_day, start_of_day
from gym.domain.enums import DurationUnit

MEMBER_CODE_MIN = 10000
MEMBER_CODE_MAX = 99999


def period_end_date(start: datetime, unit: DurationUnit, amount: int) -> datetime:
    """Fecha de vencimiento de un periodo, cerrando al final del dia.

    Equivale a Period::endDateFrom del sistema Laravel.
    """
    if amount <= 0:
        raise ValueError("La duracion debe ser mayor a cero.")

    base = start_of_day(start)
    match unit:
        case DurationUnit.DAY:
            end = base + timedelta(days=amount)
        case DurationUnit.WEEK:
            end = base + timedelta(weeks=amount)
        case DurationUnit.MONTH:
            end = add_months(base, amount)
        case _:
            raise ValueError(f"Unidad de duracion desconocida: {unit!r}")

    return end_of_day(end)


def generate_member_code(exists: Callable[[str], bool]) -> str:
    """Codigo unico de cinco digitos.

    `exists` consulta la persistencia. Se usa `secrets` en lugar de `random` para
    que los codigos no sean predecibles a partir de uno conocido.
    """
    for _ in range(100):
        code = str(secrets.randbelow(MEMBER_CODE_MAX - MEMBER_CODE_MIN + 1) + MEMBER_CODE_MIN)
        if not exists(code):
            return code
    raise RuntimeError("No fue posible generar un codigo de socio libre.")


def initials(name: str) -> str:
    """Iniciales de las dos primeras palabras del nombre."""
    words = [word for word in name.split() if word]
    return "".join(word[0].upper() for word in words[:2])


def line_subtotal_cents(unit_price_cents: int, quantity: int) -> int:
    if quantity < 1:
        raise ValueError("La cantidad debe ser al menos 1.")
    return unit_price_cents * quantity
