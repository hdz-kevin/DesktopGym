"""Catalogo de categorias y planes."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from gym.data.database import session_scope
from gym.data.models import Member, Payment, Plan, PlanCategory
from gym.domain.enums import DurationUnit
from gym.services.errors import NotFoundError, ServiceError, ValidationError


def list_plan_categories() -> list[PlanCategory]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(PlanCategory)
                .options(selectinload(PlanCategory.plans))
                .order_by(PlanCategory.name)
            ).all()
        )


def list_plans(category_id: int | None = None) -> list[Plan]:
    with session_scope() as session:
        statement = (
            select(Plan)
            .options(selectinload(Plan.plan_category))
            .join(PlanCategory)
            .order_by(PlanCategory.name, Plan.id)
        )
        if category_id is not None:
            statement = statement.where(Plan.plan_category_id == category_id)
        return list(session.scalars(statement).all())


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

        assigned = session.scalar(
            select(func.count()).select_from(Member).where(Member.plan_category_id == category_id)
        )
        if assigned:
            raise ServiceError("No se puede eliminar una categoría con socios asignados.")

        has_plans = session.scalar(
            select(func.count()).select_from(Plan).where(Plan.plan_category_id == category_id)
        )
        if has_plans:
            raise ServiceError("No se puede eliminar una categoría que tiene planes.")
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
