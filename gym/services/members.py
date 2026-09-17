"""Casos de uso de socios."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from gym.config import photos_dir
from gym.data.database import session_scope
from gym.data.models import Member, Payment, Plan, PlanCategory
from gym.domain.enums import MemberGender, MemberStatus
from gym.domain.rules import generate_member_code
from gym.services.errors import NotFoundError, ServiceError, ValidationError

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 5 * 1024 * 1024
JPEG_MAGIC = b"\xff\xd8"


@dataclass
class MemberForm:
    name: str
    gender: MemberGender
    plan_category_id: int
    birth_date: date | None = None
    photo_jpeg: bytes | None = None
    remove_photo: bool = False


@dataclass
class MemberStats:
    total: int = 0
    active: int = 0
    expired: int = 0


def _eager():
    """Carga por adelantado todo lo que la interfaz leera fuera de la sesion.

    Sin esto, acceder a `member.current_plan_label` despues de cerrar el
    `session_scope` lanzaria DetachedInstanceError.
    """
    return (
        selectinload(Member.plan_category),
        selectinload(Member.payments).selectinload(Payment.plan).selectinload(Plan.plan_category),
    )


def validate(form: MemberForm) -> dict[str, str]:
    errors: dict[str, str] = {}

    name = form.name.strip()
    if not name:
        errors["name"] = "El nombre es obligatorio."
    elif len(name) < 3:
        errors["name"] = "El nombre debe tener al menos 3 caracteres."
    elif len(name) > 255:
        errors["name"] = "El nombre es demasiado largo."

    if not form.plan_category_id:
        errors["plan_category"] = "La categoría es obligatoria."

    if form.birth_date:
        if form.birth_date > date.today():
            errors["birth_date"] = "La fecha de nacimiento no puede ser futura."
        elif form.birth_date.year < 1900:
            errors["birth_date"] = "Revisa la fecha de nacimiento."

    if form.photo_jpeg is not None:
        data = form.photo_jpeg
        if not data:
            errors["photo"] = "No se pudo guardar la foto. Intenta tomarla de nuevo."
        elif not data.startswith(JPEG_MAGIC):
            errors["photo"] = "La foto no es válida. Intenta tomarla de nuevo."
        elif len(data) > MAX_PHOTO_BYTES:
            errors["photo"] = "La foto no debe pesar más de 5 MB."

    return errors


def _store_photo(data: bytes) -> str:
    """Escribe el JPEG ya comprimido una sola vez, con nombre unico."""
    target_name = f"{uuid.uuid4().hex}.jpg"
    (photos_dir() / target_name).write_bytes(data)
    return target_name


def _delete_photo(name: str | None) -> None:
    if not name:
        return
    try:
        (photos_dir() / name).unlink(missing_ok=True)
    except OSError:
        logger.warning("No se pudo borrar la foto %s", name)


def photo_path(name: str | None) -> Path | None:
    if not name:
        return None
    path = photos_dir() / name
    return path if path.exists() else None


def _require_category(session, category_id: int) -> None:
    if session.get(PlanCategory, category_id) is None:
        raise ValidationError({"plan_category": "La categoría seleccionada ya no existe."})


def create_member(form: MemberForm) -> int:
    errors = validate(form)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        _require_category(session, form.plan_category_id)
        code = generate_member_code(
            lambda candidate: (
                session.scalar(
                    select(func.count()).select_from(Member).where(Member.code == candidate)
                )
                > 0
            )
        )
        member = Member(
            name=form.name.strip(),
            code=code,
            gender=form.gender,
            birth_date=form.birth_date,
            plan_category_id=form.plan_category_id,
            photo=_store_photo(form.photo_jpeg) if form.photo_jpeg is not None else None,
        )
        session.add(member)
        session.flush()
        logger.info("Socio creado: %s (%s)", member.name, member.code)
        return member.id


def update_member(member_id: int, form: MemberForm) -> None:
    errors = validate(form)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        _require_category(session, form.plan_category_id)
        member.name = form.name.strip()
        member.gender = form.gender
        member.birth_date = form.birth_date
        member.plan_category_id = form.plan_category_id

        if form.remove_photo:
            _delete_photo(member.photo)
            member.photo = None
        elif form.photo_jpeg is not None:
            previous = member.photo
            member.photo = _store_photo(form.photo_jpeg)
            _delete_photo(previous)

        logger.info("Socio actualizado: %s (%s)", member.name, member.code)


def delete_member(member_id: int) -> None:
    """Borra un socio solo si nunca tuvo pagos.

    Con historial de cobros de por medio, borrarlo dejaria huecos en los cortes
    de caja ya emitidos.
    """
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        has_history = session.scalar(
            select(func.count()).select_from(Payment).where(Payment.member_id == member_id)
        )
        if has_history:
            raise ServiceError("No se puede eliminar un socio con pagos registrados.")

        _delete_photo(member.photo)
        session.delete(member)
        logger.info("Socio eliminado: %s", member_id)


def _apply_filters(statement, search: str, status: MemberStatus | None):
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(Member.name.ilike(pattern), Member.code.like(pattern)))
    if status is not None:
        statement = statement.where(Member.status == status.value)
    return statement


def list_members(
    search: str = "",
    status: MemberStatus | None = None,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Member], int]:
    with session_scope() as session:
        base = select(Member)
        total = session.scalar(
            _apply_filters(select(func.count()).select_from(Member), search, status)
        )
        rows = session.scalars(
            _apply_filters(base, search, status)
            .options(*_eager())
            .order_by(Member.created_at.desc(), Member.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), int(total or 0)


def get_member(member_id: int) -> Member:
    with session_scope() as session:
        member = session.scalar(select(Member).where(Member.id == member_id).options(*_eager()))
        if member is None:
            raise NotFoundError("El socio ya no existe.")
        return member


def find_by_code(code: str) -> Member | None:
    with session_scope() as session:
        member = session.scalar(
            select(Member).where(Member.code == code.strip()).options(*_eager())
        )
        return member


def member_stats() -> MemberStats:
    with session_scope() as session:
        counts = dict(
            session.execute(
                select(Member.status, func.count()).select_from(Member).group_by(Member.status)
            ).all()
        )
        return MemberStats(
            total=sum(counts.values()),
            active=counts.get(MemberStatus.ACTIVE.value, 0),
            expired=counts.get(MemberStatus.EXPIRED.value, 0),
        )
