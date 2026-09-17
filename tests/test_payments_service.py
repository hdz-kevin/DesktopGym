from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from gym.domain.enums import DurationUnit, MemberStatus
from gym.services import members as members_service
from gym.services import payments as service
from gym.services import plans as plans_service
from gym.services.errors import NotFoundError, ValidationError
from tests.conftest import default_category_id


def alta(nombre: str = "Ana Lopez", category_id: int | None = None) -> int:
    return members_service.create_member(
        members_service.MemberForm(
            name=nombre,
            plan_category_id=category_id or default_category_id(),
        )
    )


class TestCobrar:
    def test_registra_el_primer_pago(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])

        member = members_service.get_member(member_id)
        assert len(member.payments) == 1
        assert member.status is MemberStatus.ACTIVE

    def test_copia_el_precio_del_plan(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])

        assert members_service.get_member(member_id).payments[0].price_paid_cents == 40000

    def test_calcula_el_vencimiento_segun_el_plan(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"], start=date(2025, 1, 15))

        pago = members_service.get_member(member_id).payments[0]
        assert pago.start_date.date() == date(2025, 1, 15)
        assert pago.end_date.date() == date(2025, 2, 15)

    def test_socio_inexistente(self, app_db, app_catalog):
        with pytest.raises(NotFoundError):
            service.charge(999, app_catalog["monthly_id"])

    def test_plan_inexistente(self, app_db, app_catalog):
        with pytest.raises(NotFoundError):
            service.charge(alta(category_id=app_catalog["category_id"]), 999)

    def test_rechaza_plan_de_otra_categoria(self, app_db, app_catalog):
        student_id = plans_service.create_plan_category("Estudiante")
        plans_service.create_plan(student_id, "Mensual", 1, DurationUnit.MONTH, 35000)
        member_id = alta(category_id=student_id)
        with pytest.raises(ValidationError, match="categoría"):
            service.charge(member_id, app_catalog["monthly_id"])
        assert members_service.get_member(member_id).payments == []


class TestRenovar:
    def test_agrega_un_pago(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])
        service.charge(member_id, app_catalog["monthly_id"])

        assert len(members_service.get_member(member_id).payments) == 2

    def test_si_sigue_vigente_encadena_al_dia_siguiente(self, app_db, app_catalog):
        """Cobrar antes de vencer no debe regalar ni cobrar dias dos veces."""
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])
        service.charge(member_id, app_catalog["monthly_id"])

        pagos = sorted(members_service.get_member(member_id).payments, key=lambda p: p.start_date)
        assert pagos[1].start_date.date() == pagos[0].end_date.date() + timedelta(days=1)

    def test_si_ya_vencio_empieza_hoy(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"], start=date(2020, 1, 1))
        service.charge(member_id, app_catalog["monthly_id"])

        pagos = sorted(members_service.get_member(member_id).payments, key=lambda p: p.start_date)
        assert pagos[1].start_date.date() == date.today()

    def test_reactiva_un_socio_vencido(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"], start=date(2020, 1, 1))
        assert members_service.get_member(member_id).status is MemberStatus.EXPIRED

        service.charge(member_id, app_catalog["monthly_id"])
        assert members_service.get_member(member_id).status is MemberStatus.ACTIVE

    def test_acepta_una_fecha_explicita(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])
        elegida = date.today() + timedelta(days=90)
        service.charge(member_id, app_catalog["biweekly_id"], start=elegida)

        pagos = sorted(members_service.get_member(member_id).payments, key=lambda p: p.start_date)
        assert pagos[-1].start_date.date() == elegida
        assert pagos[-1].end_date.date() == elegida + timedelta(days=14)

    def test_suma_el_total_pagado(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])
        service.charge(member_id, app_catalog["biweekly_id"])

        assert members_service.get_member(member_id).total_paid_cents == 65000

    def test_cambiar_categoria_no_reescribe_pagos_viejos(self, app_db, app_catalog):
        student_id = plans_service.create_plan_category("Estudiante")
        student_month = plans_service.create_plan(
            student_id, "Mensual", 1, DurationUnit.MONTH, 35000
        )
        member_id = alta(category_id=student_id)
        service.charge(member_id, student_month)

        member = members_service.get_member(member_id)
        members_service.update_member(
            member_id,
            members_service.MemberForm(
                name=member.name,
                plan_category_id=app_catalog["category_id"],
            ),
        )
        service.charge(member_id, app_catalog["monthly_id"])

        member = members_service.get_member(member_id)
        planes = [p.plan.label for p in member.payments]
        assert "Estudiante · Mensual" in planes
        assert "General · Mensual" in planes
        assert member.plan_category_id == app_catalog["category_id"]


class TestEstadoDelSocio:
    def test_con_pago_vigente_esta_activo(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"])
        member = members_service.get_member(member_id)
        assert member.status is MemberStatus.ACTIVE
        assert member.payments[0].is_current

    def test_con_pago_pasado_esta_vencido(self, app_db, app_catalog):
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"], start=date(2020, 1, 1))
        member = members_service.get_member(member_id)
        assert member.status is MemberStatus.EXPIRED
        assert not member.payments[0].is_current

    def test_pago_que_vence_hoy_sigue_activo(self, app_db, app_catalog):
        inicio = date.today() - timedelta(days=30)
        member_id = alta(category_id=app_catalog["category_id"])
        service.charge(member_id, app_catalog["monthly_id"], start=inicio)
        member = members_service.get_member(member_id)
        pago = member.payments[0]

        if pago.end_date.date() == date.today():
            assert member.status is MemberStatus.ACTIVE
            assert pago.is_current
            assert pago.end_date > datetime.now()
