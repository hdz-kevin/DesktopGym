"""Verificacion de acceso en el mostrador."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gym.data.models import Member, Payment
from gym.domain.dates import humanize_delta
from gym.domain.enums import MemberStatus
from gym.services import members as members_service

CODE_LENGTH = 5


@dataclass
class CheckInResult:
    granted: bool
    message: str
    member: Member | None = None
    payment: Payment | None = None
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

    payment = member.recent_payment
    if member.status is MemberStatus.EXPIRED:
        if payment is None:
            return CheckInResult(
                False,
                "Este socio no tiene un periodo vigente.",
                member=member,
                detail="Sin pagos registrados",
            )
        return CheckInResult(
            False,
            "Este socio no tiene un periodo vigente.",
            member=member,
            payment=payment,
            detail=f"Venció hace {humanize_delta(payment.end_date, now)}.",
        )

    detail = ""
    if payment:
        detail = f"Vence en {humanize_delta(payment.end_date, now)}."

    return CheckInResult(
        True,
        "¡Bienvenido!",
        member=member,
        payment=payment,
        detail=detail,
    )
