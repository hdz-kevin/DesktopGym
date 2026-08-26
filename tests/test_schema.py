"""La migracion del catalogo debe conservar datos de bases ya existentes."""

from __future__ import annotations

from alembic import command

from gym.data import database
from gym.data.schema import _alembic_config
from gym.services import memberships as memberships_service


def test_renombra_el_catalogo_sin_perder_datos(tmp_path, monkeypatch):
    """Una base del esquema inicial sigue usable despues de actualizar."""
    monkeypatch.setenv("GYM_DATA_DIR", str(tmp_path))
    database.dispose_engine()
    engine = database.init_engine()
    config = _alembic_config()

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "e3c75012dc99")

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO membership_types (id, name, created_at, updated_at) "
            "VALUES (1, 'General', '2026-01-01', '2026-01-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO durations (id, membership_type_id, name, amount, unit, "
            "price_cents, created_at, updated_at) "
            "VALUES (10, 1, 'Mensual', 1, 'month', 40000, '2026-01-01', '2026-01-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO members (id, name, code, gender, created_at, updated_at) "
            "VALUES (1, 'Ana Lopez', '12345', 'female', '2026-01-01', '2026-01-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO memberships (id, member_id, membership_type_id, "
            "created_at, updated_at) "
            "VALUES (1, 1, 1, '2026-01-01', '2026-01-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO periods (id, membership_id, duration_id, start_date, "
            "end_date, price_paid_cents, created_at, updated_at) "
            "VALUES (1, 1, 10, '2026-01-01', '2026-02-01', 40000, "
            "'2026-01-01', '2026-01-01')"
        )

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    categories = memberships_service.list_plan_categories()
    plans = memberships_service.list_plans()
    membership = memberships_service.get_membership(1)

    assert [c.name for c in categories] == ["General"]
    assert [(p.plan_category.name, p.name, p.price_cents) for p in plans] == [
        ("General", "Mensual", 40000)
    ]
    assert membership.plan_category.name == "General"
    assert membership.payments[0].plan.name == "Mensual"

    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "plan_categories" in tables
    assert "plans" in tables
    assert "payments" in tables
    assert "membership_types" not in tables
    assert "durations" not in tables
    assert "periods" not in tables

    database.dispose_engine()
