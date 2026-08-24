"""Casos de uso de membresias, periodos y catalogo de precios."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from gym.data.database import session_scope
from gym.data.models import Duration, Member, Membership, MembershipType, Period
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
        selectinload(Membership.membership_type),
        selectinload(Membership.periods).selectinload(Period.duration),
    )


def _load_duration(session, duration_id: int) -> Duration:
    duration = session.get(Duration, duration_id)
    if duration is None:
        raise NotFoundError("La duración seleccionada ya no existe.")
    return duration


def create_membership(member_id: int, duration_id: int, start: date | None = None) -> int:
    """Da de alta una membresia con su primer periodo pagado.

    El precio se copia de la duracion al periodo: cambiar la lista de precios
    despues no debe alterar lo que este socio ya pago.
    """
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        duration = _load_duration(session, duration_id)

        membership = Membership(member_id=member_id, membership_type_id=duration.membership_type_id)
        session.add(membership)
        session.flush()

        begins = start_of_day(start or date.today())
        session.add(
            Period(
                membership_id=membership.id,
                duration_id=duration.id,
                start_date=begins,
                end_date=period_end_date(begins, duration.unit, duration.amount),
                price_paid_cents=duration.price_cents,
            )
        )
        logger.info("Membresia creada para el socio %s", member_id)
        return membership.id


def renew_membership(membership_id: int, duration_id: int, start: date | None = None) -> int:
    """Agrega un periodo nuevo.

    Si la membresia sigue vigente, el periodo arranca al dia siguiente del
    vencimiento actual para no regalar ni cobrar dias dos veces.
    """
    with session_scope() as session:
        membership = session.get(Membership, membership_id)
        if membership is None:
            raise NotFoundError("La membresía ya no existe.")

        duration = _load_duration(session, duration_id)

        if start is not None:
            begins = start_of_day(start)
        else:
            last_end = session.scalar(
                select(func.max(Period.end_date)).where(Period.membership_id == membership_id)
            )
            now = datetime.now()
            if last_end and last_end > now:
                begins = start_of_day(last_end) + timedelta(days=1)
            else:
                begins = start_of_day(now)

        period = Period(
            membership_id=membership_id,
            duration_id=duration.id,
            start_date=begins,
            end_date=period_end_date(begins, duration.unit, duration.amount),
            price_paid_cents=duration.price_cents,
        )
        session.add(period)
        session.flush()
        logger.info("Membresia %s renovada", membership_id)
        return period.id


def update_period(period_id: int, duration_id: int, start: date, price_cents: int) -> None:
    """Corrige un periodo ya registrado, por ejemplo tras un cobro mal capturado."""
    if price_cents < 0:
        raise ValidationError({"price": "El precio no puede ser negativo."})

    with session_scope() as session:
        period = session.get(Period, period_id)
        if period is None:
            raise NotFoundError("El periodo ya no existe.")

        duration = _load_duration(session, duration_id)
        begins = start_of_day(start)

        period.duration_id = duration.id
        period.start_date = begins
        period.end_date = period_end_date(begins, duration.unit, duration.amount)
        period.price_paid_cents = price_cents
        logger.info("Periodo %s actualizado", period_id)


def delete_period(period_id: int) -> None:
    """Elimina un periodo capturado por error.

    Se impide borrar el ultimo: una membresia sin periodos no tendria forma de
    calcular su estado ni su historial de pagos.
    """
    with session_scope() as session:
        period = session.get(Period, period_id)
        if period is None:
            raise NotFoundError("El periodo ya no existe.")

        remaining = session.scalar(
            select(func.count())
            .select_from(Period)
            .where(Period.membership_id == period.membership_id)
        )
        if remaining <= 1:
            raise ServiceError(
                "No se puede eliminar el único periodo de una membresía. "
                "Elimina la membresía completa si fue un error."
            )
        session.delete(period)


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


def list_membership_types() -> list[MembershipType]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(MembershipType)
                .options(selectinload(MembershipType.durations))
                .order_by(MembershipType.name)
            ).all()
        )


def list_durations() -> list[Duration]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(Duration)
                .options(selectinload(Duration.membership_type))
                .join(MembershipType)
                .order_by(MembershipType.name, Duration.id)
            ).all()
        )


def create_membership_type(name: str) -> int:
    name = name.strip()
    if not name:
        raise ValidationError({"name": "El nombre es obligatorio."})

    with session_scope() as session:
        exists = session.scalar(
            select(func.count())
            .select_from(MembershipType)
            .where(func.lower(MembershipType.name) == name.lower())
        )
        if exists:
            raise ValidationError({"name": f'Ya existe un tipo llamado "{name}".'})

        membership_type = MembershipType(name=name)
        session.add(membership_type)
        session.flush()
        return membership_type.id


def rename_membership_type(type_id: int, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValidationError({"name": "El nombre es obligatorio."})

    with session_scope() as session:
        membership_type = session.get(MembershipType, type_id)
        if membership_type is None:
            raise NotFoundError("El tipo de membresía ya no existe.")

        clash = session.scalar(
            select(func.count())
            .select_from(MembershipType)
            .where(
                func.lower(MembershipType.name) == name.lower(),
                MembershipType.id != type_id,
            )
        )
        if clash:
            raise ValidationError({"name": f'Ya existe un tipo llamado "{name}".'})

        membership_type.name = name


def delete_membership_type(type_id: int) -> None:
    with session_scope() as session:
        membership_type = session.get(MembershipType, type_id)
        if membership_type is None:
            raise NotFoundError("El tipo de membresía ya no existe.")

        in_use = session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.membership_type_id == type_id)
        )
        if in_use:
            raise ServiceError("No se puede eliminar un tipo con membresías registradas.")
        session.delete(membership_type)


def validate_duration(name: str, amount: int, price_cents: int) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not name.strip():
        errors["name"] = "El nombre es obligatorio."
    if amount <= 0:
        errors["amount"] = "La cantidad debe ser mayor a cero."
    if price_cents < 0:
        errors["price"] = "El precio no puede ser negativo."
    return errors


def create_duration(
    type_id: int, name: str, amount: int, unit: DurationUnit, price_cents: int
) -> int:
    errors = validate_duration(name, amount, price_cents)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        if session.get(MembershipType, type_id) is None:
            raise NotFoundError("El tipo de membresía ya no existe.")

        duration = Duration(
            membership_type_id=type_id,
            name=name.strip(),
            amount=amount,
            unit=unit,
            price_cents=price_cents,
        )
        session.add(duration)
        session.flush()
        return duration.id


def update_duration(
    duration_id: int, name: str, amount: int, unit: DurationUnit, price_cents: int
) -> None:
    """Cambia una duracion del catalogo.

    Los periodos ya cobrados conservan su `price_paid_cents`, asi que subir el
    precio no reescribe la historia.
    """
    errors = validate_duration(name, amount, price_cents)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        duration = session.get(Duration, duration_id)
        if duration is None:
            raise NotFoundError("La duración ya no existe.")

        duration.name = name.strip()
        duration.amount = amount
        duration.unit = unit
        duration.price_cents = price_cents


def delete_duration(duration_id: int) -> None:
    with session_scope() as session:
        duration = session.get(Duration, duration_id)
        if duration is None:
            raise NotFoundError("La duración ya no existe.")

        in_use = session.scalar(
            select(func.count()).select_from(Period).where(Period.duration_id == duration_id)
        )
        if in_use:
            raise ServiceError(
                "No se puede eliminar una duración usada en periodos ya registrados."
            )
        session.delete(duration)
