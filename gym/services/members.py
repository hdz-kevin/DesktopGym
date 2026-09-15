"""Casos de uso de socios."""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from gym.config import photos_dir
from gym.data.database import session_scope
from gym.data.models import Member, Membership, Payment, Plan
from gym.domain.enums import MemberGender, MemberStatus
from gym.domain.rules import generate_member_code
from gym.services.errors import NotFoundError, ServiceError, ValidationError

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class MemberForm:
    name: str
    gender: MemberGender
    birth_date: date | None = None
    photo_source: Path | None = None
    remove_photo: bool = False


@dataclass
class MemberStats:
    total: int = 0
    active: int = 0
    expired: int = 0
    without_membership: int = 0


def _eager():
    """Carga por adelantado todo lo que la interfaz leera fuera de la sesion.

    Sin esto, acceder a `member.memberships[0].current_plan_label` despues de
    cerrar el `session_scope` lanzaria DetachedInstanceError.
    """
    return (
        selectinload(Member.memberships).selectinload(Membership.plan_category),
        selectinload(Member.memberships)
        .selectinload(Membership.payments)
        .selectinload(Payment.plan)
        .selectinload(Plan.plan_category),
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

    if form.birth_date:
        if form.birth_date > date.today():
            errors["birth_date"] = "La fecha de nacimiento no puede ser futura."
        elif form.birth_date.year < 1900:
            errors["birth_date"] = "Revisa la fecha de nacimiento."

    if form.photo_source is not None:
        source = form.photo_source
        if not source.exists():
            errors["photo"] = "No se encontró el archivo de la foto."
        elif source.suffix.lower() not in ALLOWED_PHOTO_SUFFIXES:
            errors["photo"] = "Formato no admitido. Usa JPG, PNG o WEBP."
        elif source.stat().st_size > MAX_PHOTO_BYTES:
            errors["photo"] = "La foto no debe pesar más de 5 MB."

    return errors


def _store_photo(source: Path) -> str:
    """Copia la foto al area de datos con un nombre unico.

    Se renombra con UUID para que dos socios con el mismo archivo de origen no
    se pisen y para no arrastrar nombres con acentos o espacios.
    """
    target_name = f"{uuid.uuid4().hex}{source.suffix.lower()}"
    shutil.copy2(source, photos_dir() / target_name)
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


def create_member(form: MemberForm) -> int:
    errors = validate(form)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
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
            photo=_store_photo(form.photo_source) if form.photo_source else None,
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

        member.name = form.name.strip()
        member.gender = form.gender
        member.birth_date = form.birth_date

        if form.remove_photo:
            _delete_photo(member.photo)
            member.photo = None
        elif form.photo_source is not None:
            previous = member.photo
            member.photo = _store_photo(form.photo_source)
            _delete_photo(previous)

        logger.info("Socio actualizado: %s (%s)", member.name, member.code)


def delete_member(member_id: int) -> None:
    """Borra un socio solo si nunca tuvo membresias.

    Con historial de pagos de por medio, borrarlo dejaria huecos en los cortes
    de caja ya emitidos.
    """
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            raise NotFoundError("El socio ya no existe.")

        has_history = session.scalar(
            select(func.count()).select_from(Membership).where(Membership.member_id == member_id)
        )
        if has_history:
            raise ServiceError(
                "No se puede eliminar un socio con membresías registradas, "
                "porque su historial forma parte de los cortes de caja."
            )

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
            without_membership=counts.get(MemberStatus.NO_MEMBERSHIP.value, 0),
        )
