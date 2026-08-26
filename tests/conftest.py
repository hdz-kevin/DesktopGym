"""Fixtures compartidas."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from gym.config import database_path
from gym.data import database
from gym.data.database import create_db_engine
from gym.data.models import Base, Plan, PlanCategory
from gym.domain.enums import DurationUnit


@pytest.fixture
def engine():
    engine = create_db_engine(":memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Session:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    """Apunta el motor global de la aplicacion a una base temporal.

    Los servicios usan `session_scope()`, que resuelve el motor global; sin
    esto las pruebas escribirian en la base real del usuario.
    """
    monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
    database.dispose_engine()
    # Se usa la ruta real (`database_path`) y no un nombre inventado, para que
    # respaldos y restauraciones se prueben contra el archivo que usaran.
    engine = database.init_engine(database_path())
    Base.metadata.create_all(engine)
    yield engine
    database.dispose_engine()


@pytest.fixture
def catalog(session: Session) -> dict[str, Plan | PlanCategory]:
    """Una categoria de planes con dos planes para las pruebas de modelo."""
    return _build_catalog(session)


@pytest.fixture
def app_catalog(app_db) -> dict[str, int]:
    """Catalogo cargado en la base de la aplicacion, devuelto como ids."""
    factory = sessionmaker(bind=app_db, expire_on_commit=False)
    with factory() as session:
        built = _build_catalog(session)
        return {
            "category_id": built["category"].id,
            "monthly_id": built["monthly"].id,
            "biweekly_id": built["biweekly"].id,
        }


def _build_catalog(session: Session) -> dict[str, Plan | PlanCategory]:
    general = PlanCategory(name="General")
    session.add(general)
    session.flush()

    monthly = Plan(
        plan_category_id=general.id,
        name="Mensual",
        amount=1,
        unit=DurationUnit.MONTH,
        price_cents=40000,
    )
    biweekly = Plan(
        plan_category_id=general.id,
        name="2 Semanas",
        amount=2,
        unit=DurationUnit.WEEK,
        price_cents=25000,
    )
    session.add_all([monthly, biweekly])
    session.commit()
    return {"category": general, "monthly": monthly, "biweekly": biweekly}
