"""Enums de dominio, equivalentes a los de app/Enums del sistema Laravel."""

from __future__ import annotations

from enum import Enum


class DurationUnit(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    def label(self, quantity: int = 1) -> str:
        singular, plural = {
            DurationUnit.DAY: ("Día", "Días"),
            DurationUnit.WEEK: ("Semana", "Semanas"),
            DurationUnit.MONTH: ("Mes", "Meses"),
        }[self]
        return singular if quantity == 1 else plural


class MemberStatus(str, Enum):
    """Estado del socio derivado de sus pagos."""

    ACTIVE = "active"
    EXPIRED = "expired"

    def label(self) -> str:
        return "Activo" if self is MemberStatus.ACTIVE else "Vencido"
