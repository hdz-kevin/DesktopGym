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


class MemberGender(str, Enum):
    MALE = "male"
    FEMALE = "female"

    def label(self) -> str:
        return "Masculino" if self is MemberGender.MALE else "Femenino"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"

    def label(self) -> str:
        return "Activa" if self is MembershipStatus.ACTIVE else "Vencida"


class MemberStatus(str, Enum):
    """Estado del socio derivado de sus membresias."""

    ACTIVE = "active"
    EXPIRED = "expired"
    NO_MEMBERSHIP = "no_membership"

    def label(self) -> str:
        return {
            MemberStatus.ACTIVE: "Activo",
            MemberStatus.EXPIRED: "Vencido",
            MemberStatus.NO_MEMBERSHIP: "Sin membresía",
        }[self]
