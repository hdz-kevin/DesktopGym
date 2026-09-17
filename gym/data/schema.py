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
from gym.data.models import Plan, PlanCategory
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
    # connect() y no begin(): env.py apaga las FK de SQLite antes de migrar,
    # y ese PRAGMA no surte efecto dentro de una transaccion ya abierta.
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        if connection.in_transaction():
            connection.commit()
    logger.info("Esquema actualizado")


def populate_seed_catalog(session) -> None:
    """Inserta el catalogo inicial.

    El llamador garantiza que la base esta vacia.
    """
    for category_name, plans in SEED_CATALOG.items():
        category = PlanCategory(name=category_name)
        session.add(category)
        session.flush()
        for name, amount, unit, price_cents in plans:
            session.add(
                Plan(
                    plan_category_id=category.id,
                    name=name,
                    amount=amount,
                    unit=unit,
                    price_cents=price_cents,
                )
            )


def seed_catalog() -> None:
    """Crea categorias de planes y planes si el catalogo esta vacio.

    Sin esto el primer cobro seria imposible: no habria ningun precio para elegir.
    """
    with session_scope() as session:
        if session.scalar(select(PlanCategory).limit(1)) is not None:
            return
        populate_seed_catalog(session)
        logger.info("Catalogo inicial creado")


def prepare_database() -> None:
    upgrade_database()
    seed_catalog()
