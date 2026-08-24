"""Puesta al dia del esquema y datos semilla.

La aplicacion corre las migraciones sola al arrancar: el usuario final no tiene
una terminal para ejecutar Alembic a mano.
"""

from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from gym.config import resource_path
from gym.data.database import get_engine, session_scope
from gym.data.models import Duration, MembershipType
from gym.domain.enums import DurationUnit

logger = logging.getLogger(__name__)

SEED_CATALOG: dict[str, list[tuple[str, int, DurationUnit, int]]] = {
    "General": [
        ("2 Semanas", 2, DurationUnit.WEEK, 25000),
        ("Mensual", 1, DurationUnit.MONTH, 40000),
    ],
    "Estudiante": [
        ("2 Semanas", 2, DurationUnit.WEEK, 20000),
        ("Mensual", 1, DurationUnit.MONTH, 35000),
    ],
}


def _alembic_config() -> Config:
    ini = resource_path("../alembic.ini").resolve()
    if not ini.exists():
        ini = resource_path("alembic.ini").resolve()

    config = Config(str(ini))
    scripts = ini.parent / "migrations"
    config.set_main_option("script_location", str(scripts))
    return config


def upgrade_database() -> None:
    """Aplica las migraciones pendientes sobre la base del usuario."""
    engine = get_engine()
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    logger.info("Esquema actualizado")


def seed_catalog() -> None:
    """Crea tipos de membresia y duraciones si el catalogo esta vacio.

    Sin esto la primera alta de membresia seria imposible: no habria ningun
    precio para elegir.
    """
    with session_scope() as session:
        if session.scalar(select(MembershipType).limit(1)) is not None:
            return

        for type_name, durations in SEED_CATALOG.items():
            membership_type = MembershipType(name=type_name)
            session.add(membership_type)
            session.flush()
            for name, amount, unit, price_cents in durations:
                session.add(
                    Duration(
                        membership_type_id=membership_type.id,
                        name=name,
                        amount=amount,
                        unit=unit,
                        price_cents=price_cents,
                    )
                )
        logger.info("Catalogo inicial creado")


def prepare_database() -> None:
    upgrade_database()
    seed_catalog()
