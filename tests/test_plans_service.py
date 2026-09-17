from __future__ import annotations

import pytest

from gym.domain.enums import DurationUnit
from gym.services import members as members_service
from gym.services import payments as payments_service
from gym.services import plans as service
from gym.services.errors import ServiceError, ValidationError
from tests.conftest import default_category_id


def alta(nombre: str = "Ana Lopez", category_id: int | None = None) -> int:
    return members_service.create_member(
        members_service.MemberForm(
            name=nombre,
            plan_category_id=category_id or default_category_id(),
        )
    )


class TestCatalogoDePrecios:
    def test_lista_las_categorias_con_sus_planes(self, app_db, app_catalog):
        categorias = service.list_plan_categories()
        assert len(categorias) == 1
        assert len(categorias[0].plans) == 2

    def test_crea_una_categoria(self, app_db, app_catalog):
        service.create_plan_category("Premium")
        assert len(service.list_plan_categories()) == 2

    def test_no_admite_categorias_duplicadas(self, app_db, app_catalog):
        with pytest.raises(ValidationError):
            service.create_plan_category("general")

    def test_rechaza_nombre_vacio(self, app_db):
        with pytest.raises(ValidationError):
            service.create_plan_category("   ")

    def test_renombra_una_categoria(self, app_db, app_catalog):
        service.rename_plan_category(app_catalog["category_id"], "General Plus")
        assert service.list_plan_categories()[0].name == "General Plus"

    def test_no_borra_una_categoria_con_socios(self, app_db, app_catalog):
        alta(category_id=app_catalog["category_id"])
        with pytest.raises(ServiceError, match="socios asignados"):
            service.delete_plan_category(app_catalog["category_id"])

    def test_no_borra_una_categoria_con_planes(self, app_db, app_catalog):
        with pytest.raises(ServiceError, match="tiene planes"):
            service.delete_plan_category(app_catalog["category_id"])

    def test_borra_una_categoria_sin_uso(self, app_db):
        category_id = service.create_plan_category("Temporal")
        service.delete_plan_category(category_id)
        assert all(t.id != category_id for t in service.list_plan_categories())

    def test_crea_un_plan(self, app_db, app_catalog):
        service.create_plan(app_catalog["category_id"], "Trimestral", 3, DurationUnit.MONTH, 100000)
        assert len(service.list_plans()) == 3

    def test_lista_planes_de_una_categoria(self, app_db, app_catalog):
        other = service.create_plan_category("Estudiante")
        service.create_plan(other, "Mensual", 1, DurationUnit.MONTH, 35000)
        assert len(service.list_plans(app_catalog["category_id"])) == 2
        assert len(service.list_plans(other)) == 1

    @pytest.mark.parametrize(
        ("nombre", "cantidad", "precio", "campo"),
        [
            ("", 1, 1000, "name"),
            ("Mensual", 0, 1000, "amount"),
            ("Mensual", 1, -1, "price"),
        ],
    )
    def test_valida_los_planes(self, app_db, app_catalog, nombre, cantidad, precio, campo):
        with pytest.raises(ValidationError) as exc:
            service.create_plan(
                app_catalog["category_id"], nombre, cantidad, DurationUnit.MONTH, precio
            )
        assert campo in exc.value.errors

    def test_actualiza_un_plan(self, app_db, app_catalog):
        service.update_plan(app_catalog["monthly_id"], "Mensual", 1, DurationUnit.MONTH, 45000)
        mensual = next(d for d in service.list_plans() if d.id == app_catalog["monthly_id"])
        assert mensual.price_cents == 45000

    def test_subir_el_precio_no_reescribe_lo_ya_cobrado(self, app_db, app_catalog):
        """El pago guarda lo que el socio pago, no el precio de hoy."""
        member_id = alta(category_id=app_catalog["category_id"])
        payments_service.charge(member_id, app_catalog["monthly_id"])

        service.update_plan(app_catalog["monthly_id"], "Mensual", 1, DurationUnit.MONTH, 90000)

        pago = members_service.get_member(member_id).payments[0]
        assert pago.price_paid_cents == 40000

    def test_no_borra_un_plan_usado(self, app_db, app_catalog):
        payments_service.charge(
            alta(category_id=app_catalog["category_id"]), app_catalog["monthly_id"]
        )
        with pytest.raises(ServiceError, match="pagos ya registrados"):
            service.delete_plan(app_catalog["monthly_id"])

    def test_borra_un_plan_sin_uso(self, app_db, app_catalog):
        plan_id = service.create_plan(
            app_catalog["category_id"], "Anual", 12, DurationUnit.MONTH, 400000
        )
        service.delete_plan(plan_id)
        assert all(d.id != plan_id for d in service.list_plans())
