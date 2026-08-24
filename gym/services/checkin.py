"""Verificacion de acceso en el mostrador."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gym.data.models import Member, Membership
from gym.domain.dates import format_date, humanize_delta
from gym.domain.enums import MembershipStatus
from gym.services import members as members_service

CODE_LENGTH = 5


@dataclass
class CheckInResult:
    granted: bool
    message: str
    member: Member | None = None
    membership: Membership | None = None
    detail: str = ""

    @property
    def member_name(self) -> str:
        return self.member.name if self.member else ""


def verify_code(code: str, now: datetime | None = None) -> CheckInResult:
    """Resuelve si un codigo da acceso al gimnasio.

    Devuelve siempre un resultado con mensaje listo para mostrar, en vez de
    lanzar excepciones: en el mostrador un codigo mal tecleado es lo normal.
    """
    now = now or datetime.now()
    code = code.strip()

    if not code.isdigit() or len(code) != CODE_LENGTH:
        return CheckInResult(False, f"El código debe tener {CODE_LENGTH} dígitos.")

    member = members_service.find_by_code(code)
    if member is None:
        return CheckInResult(False, "No encontramos ningún socio con ese código.")

    membership = member.latest_membership()
    if membership is None:
        return CheckInResult(
            False,
            "Este socio no tiene ninguna membresía registrada.",
            member=member,
            detail="Pásalo a recepción para darlo de alta.",
        )

    if membership.status is MembershipStatus.EXPIRED:
        period = membership.recent_period
        detail = f"Venció el {format_date(period.end_date)}." if period else "Sin periodos pagados."
        return CheckInResult(
            False,
            "Membresía vencida.",
            member=member,
            membership=membership,
            detail=detail,
        )

    period = membership.recent_period
    detail = ""
    if period:
        detail = f"Vence en {humanize_delta(period.end_date, now)}."

    return CheckInResult(
        True,
        "¡Bienvenido!",
        member=member,
        membership=membership,
        detail=detail,
    )
