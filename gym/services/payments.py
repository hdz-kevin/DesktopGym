"""Cobros de planes: un pago es un periodo de vigencia del socio."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from gym.data.database import session_scope
from gym.data.models import Member, Payment, Plan
from gym.domain.dates import start_of_day
from gym.domain.rules import period_end_date
from gym.services.errors import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def _load_plan(session, plan_id: int) -> Plan:
    plan = session.scalar(
        select(Plan).where(Plan.id == plan_id).options(selectinload(Plan.plan_category))
    )
    if plan is None:
        raise NotFoundError("El plan seleccionado ya no existe.")
    return plan


def charge(member_id: int, plan_id: int, start: date | None = None) -> int:
    """Registra un pago del socio.

    El precio se copia del plan: cambiar la lista de precios despues no debe
    alterar lo que este socio ya pago. Si sigue vigente, el nuevo periodo
    arranca al dia siguiente del vencimiento actual para no regalar ni cobrar
    dias dos veces.
    """
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        plan = _load_plan(session, plan_id)
        if plan.plan_category_id != member.plan_category_id:
            raise ValidationError({"plan": "Ese plan no corresponde a la categoría del socio."})

        if start is not None:
            begins = start_of_day(start)
        else:
            last_end = session.scalar(
                select(func.max(Payment.end_date)).where(Payment.member_id == member_id)
            )
            now = datetime.now()
            if last_end and last_end > now:
                begins = start_of_day(last_end) + timedelta(days=1)
            else:
                begins = start_of_day(now)

        payment = Payment(
            member_id=member_id,
            plan_id=plan.id,
            start_date=begins,
            end_date=period_end_date(begins, plan.unit, plan.amount),
            price_paid_cents=plan.price_cents,
        )
        session.add(payment)
        session.flush()
        logger.info("Pago %s registrado para el socio %s", payment.id, member_id)
        return payment.id
