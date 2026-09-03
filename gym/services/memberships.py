"""Casos de uso de membresias, pagos y catalogo de precios."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from gym.data.database import session_scope
from gym.data.models import Member, Membership, Payment, Plan, PlanCategory
from gym.domain.dates import start_of_day
from gym.domain.enums import DurationUnit, MembershipStatus
from gym.domain.rules import period_end_date
from gym.services.errors import NotFoundError, ServiceError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class MembershipStats:
    total: int = 0
    active: int = 0
    expired: int = 0


def _eager():
    return (
        selectinload(Membership.member),
        selectinload(Membership.plan_category),
        selectinload(Membership.payments)
        .selectinload(Payment.plan)
        .selectinload(Plan.plan_category),
    )


def _load_plan(session, plan_id: int) -> Plan:
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("El plan seleccionado ya no existe.")
    return plan


def create_membership(member_id: int, plan_id: int, start: date | None = None) -> int:
    """Da de alta una membresia con su primer pago.

    El precio se copia del plan al pago: cambiar la lista de precios despues
    no debe alterar lo que este socio ya pago.
    """
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        plan = _load_plan(session, plan_id)

        membership = Membership(member_id=member_id, plan_category_id=plan.plan_category_id)
        session.add(membership)
        session.flush()

        begins = start_of_day(start or date.today())
        session.add(
            Payment(
                membership_id=membership.id,
                plan_id=plan.id,
                start_date=begins,
                end_date=period_end_date(begins, plan.unit, plan.amount),
                price_paid_cents=plan.price_cents,
            )
        )
        logger.info("Membresia creada para el socio %s", member_id)
        return membership.id


def renew_membership(membership_id: int, plan_id: int, start: date | None = None) -> int:
    """Registra un pago nuevo.

    Si la membresia sigue vigente, la vigencia arranca al dia siguiente del
    vencimiento actual para no regalar ni cobrar dias dos veces.
    """
    with session_scope() as session:
        membership = session.get(Membership, membership_id)
        if membership is None:
            raise NotFoundError("La membresía ya no existe.")

        plan = _load_plan(session, plan_id)
        membership.plan_category_id = plan.plan_category_id

        if start is not None:
            begins = start_of_day(start)
        else:
            last_end = session.scalar(
                select(func.max(Payment.end_date)).where(Payment.membership_id == membership_id)
            )
            now = datetime.now()
            if last_end and last_end > now:
                begins = start_of_day(last_end) + timedelta(days=1)
            else:
                begins = start_of_day(now)

        payment = Payment(
            membership_id=membership_id,
            plan_id=plan.id,
            start_date=begins,
            end_date=period_end_date(begins, plan.unit, plan.amount),
            price_paid_cents=plan.price_cents,
        )
        session.add(payment)
        session.flush()
        logger.info("Membresia %s renovada", membership_id)
        return payment.id


def delete_membership(membership_id: int) -> None:
    with session_scope() as session:
        membership = session.get(Membership, membership_id)
        if membership is None:
            raise NotFoundError("La membresía ya no existe.")
        session.delete(membership)
        logger.info("Membresia %s eliminada", membership_id)


def _apply_filters(statement, search: str, status: MembershipStatus | None):
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.join(Member, Membership.member_id == Member.id).where(
            or_(Member.name.ilike(pattern), Member.code.like(pattern))
        )
    if status is not None:
        statement = statement.where(Membership.status == status.value)
    return statement


def list_memberships(
    search: str = "",
    status: MembershipStatus | None = None,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Membership], int]:
    with session_scope() as session:
        total = session.scalar(
            _apply_filters(select(func.count()).select_from(Membership), search, status)
        )
        rows = session.scalars(
            _apply_filters(select(Membership), search, status)
            .options(*_eager())
            .order_by(Membership.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), int(total or 0)


def get_membership(membership_id: int) -> Membership:
    with session_scope() as session:
        membership = session.scalar(
            select(Membership).where(Membership.id == membership_id).options(*_eager())
        )
        if membership is None:
            raise NotFoundError("La membresía ya no existe.")
        return membership


def membership_stats() -> MembershipStats:
    with session_scope() as session:
        counts = dict(
            session.execute(
                select(Membership.status, func.count())
                .select_from(Membership)
                .group_by(Membership.status)
            ).all()
        )
        return MembershipStats(
            total=sum(counts.values()),
            active=counts.get(MembershipStatus.ACTIVE.value, 0),
            expired=counts.get(MembershipStatus.EXPIRED.value, 0),
        )


def search_members(term: str, limit: int = 10) -> list[Member]:
    """Autocompletado de socios al crear una membresia."""
    term = term.strip()
    if not term:
        return []

    with session_scope() as session:
        pattern = f"%{term}%"
        return list(
            session.scalars(
                select(Member)
                .where(or_(Member.name.ilike(pattern), Member.code.like(pattern)))
                .order_by(Member.name)
                .limit(limit)
            ).all()
        )


# --- Catalogo de precios -------------------------------------------------


def list_plan_categories() -> list[PlanCategory]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(PlanCategory)
                .options(selectinload(PlanCategory.plans))
                .order_by(PlanCategory.name)
            ).all()
        )


def list_plans() -> list[Plan]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(Plan)
                .options(selectinload(Plan.plan_category))
                .join(PlanCategory)
                .order_by(PlanCategory.name, Plan.id)
            ).all()
        )


def create_plan_category(name: str) -> int:
    name = name.strip()
    if not name:
        raise ValidationError({"name": "El nombre es obligatorio."})

    with session_scope() as session:
        exists = session.scalar(
            select(func.count())
            .select_from(PlanCategory)
            .where(func.lower(PlanCategory.name) == name.lower())
        )
        if exists:
            raise ValidationError({"name": f'Ya existe una categoría llamada "{name}".'})

        category = PlanCategory(name=name)
        session.add(category)
        session.flush()
        return category.id


def rename_plan_category(category_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValidationError({"name": "El nombre es obligatorio."})

    with session_scope() as session:
        category = session.get(PlanCategory, category_id)
        if category is None:
            raise NotFoundError("La categoría de planes ya no existe.")

        clash = session.scalar(
            select(func.count())
            .select_from(PlanCategory)
            .where(
                func.lower(PlanCategory.name) == name.lower(),
                PlanCategory.id != category_id,
            )
        )
        if clash:
            raise ValidationError({"name": f'Ya existe una categoría llamada "{name}".'})

        category.name = name


def delete_plan_category(category_id: int) -> None:
    with session_scope() as session:
        category = session.get(PlanCategory, category_id)
        if category is None:
            raise NotFoundError("La categoría de planes ya no existe.")

        in_use = session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.plan_category_id == category_id)
        )
        if in_use:
            raise ServiceError("No se puede eliminar una categoría con membresías registradas.")
        session.delete(category)


def validate_plan(name: str, amount: int, price_cents: int) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not name.strip():
        errors["name"] = "El nombre es obligatorio."
    if amount <= 0:
        errors["amount"] = "La cantidad debe ser mayor a cero."
    if price_cents < 0:
        errors["price"] = "El precio no puede ser negativo."
    return errors


def create_plan(
    category_id: int, name: str, amount: int, unit: DurationUnit, price_cents: int
) -> int:
    errors = validate_plan(name, amount, price_cents)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        if session.get(PlanCategory, category_id) is None:
            raise NotFoundError("La categoría de planes ya no existe.")

        plan = Plan(
            plan_category_id=category_id,
            name=name.strip(),
            amount=amount,
            unit=unit,
            price_cents=price_cents,
        )
        session.add(plan)
        session.flush()
        return plan.id


def update_plan(plan_id: int, name: str, amount: int, unit: DurationUnit, price_cents: int) -> None:
    """Cambia un plan del catalogo.

    Los pagos ya cobrados conservan su `price_paid_cents`, asi que subir el
    precio no reescribe la historia.
    """
    errors = validate_plan(name, amount, price_cents)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        plan = session.get(Plan, plan_id)
        if plan is None:
            raise NotFoundError("El plan ya no existe.")

        plan.name = name.strip()
        plan.amount = amount
        plan.unit = unit
        plan.price_cents = price_cents


def delete_plan(plan_id: int) -> None:
    with session_scope() as session:
        plan = session.get(Plan, plan_id)
        if plan is None:
            raise NotFoundError("El plan ya no existe.")

        in_use = session.scalar(
            select(func.count()).select_from(Payment).where(Payment.plan_id == plan_id)
        )
        if in_use:
            raise ServiceError("No se puede eliminar un plan usado en pagos ya registrados.")
        session.delete(plan)
