from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from gym.domain.enums import DurationUnit, MemberGender, MembershipStatus, PeriodStatus
from gym.services import members as members_service
from gym.services import memberships as service
from gym.services.errors import NotFoundError, ServiceError, ValidationError


def alta(nombre: str = "Ana Lopez") -> int:
    return members_service.create_member(
        members_service.MemberForm(name=nombre, gender=MemberGender.FEMALE)
    )


class TestCrearMembresia:
    def test_crea_membresia_con_su_primer_periodo(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])

        membership = service.get_membership(membership_id)
        assert len(membership.periods) == 1
        assert membership.status is MembershipStatus.ACTIVE

    def test_copia_el_precio_del_plan(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])

        periodo = service.get_membership(membership_id).periods[0]
        assert periodo.price_paid_cents == 40000

    def test_calcula_el_vencimiento_segun_el_plan(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(
            member_id, app_catalog["monthly_id"], start=date(2025, 1, 15)
        )

        periodo = service.get_membership(membership_id).periods[0]
        assert periodo.start_date.date() == date(2025, 1, 15)
        assert periodo.end_date.date() == date(2025, 2, 15)

    def test_el_socio_queda_activo(self, app_db, app_catalog):
        member_id = alta()
        service.create_membership(member_id, app_catalog["monthly_id"])

        from gym.domain.enums import MemberStatus

        assert members_service.get_member(member_id).status is MemberStatus.ACTIVE

    def test_socio_inexistente(self, app_db, app_catalog):
        with pytest.raises(NotFoundError):
            service.create_membership(999, app_catalog["monthly_id"])

    def test_plan_inexistente(self, app_db):
        with pytest.raises(NotFoundError):
            service.create_membership(alta(), 999)


class TestRenovar:
    def test_agrega_un_periodo(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        service.renew_membership(membership_id, app_catalog["monthly_id"])

        assert len(service.get_membership(membership_id).periods) == 2

    def test_si_sigue_vigente_encadena_al_dia_siguiente(self, app_db, app_catalog):
        """Renovar antes de vencer no debe regalar ni cobrar dias dos veces."""
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        service.renew_membership(membership_id, app_catalog["monthly_id"])

        periodos = sorted(service.get_membership(membership_id).periods, key=lambda p: p.start_date)
        assert periodos[1].start_date.date() == periodos[0].end_date.date() + timedelta(days=1)

    def test_si_ya_vencio_empieza_hoy(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(
            member_id, app_catalog["monthly_id"], start=date(2020, 1, 1)
        )
        service.renew_membership(membership_id, app_catalog["monthly_id"])

        periodos = sorted(service.get_membership(membership_id).periods, key=lambda p: p.start_date)
        assert periodos[1].start_date.date() == date.today()

    def test_renovar_reactiva_una_membresia_vencida(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(
            member_id, app_catalog["monthly_id"], start=date(2020, 1, 1)
        )
        assert service.get_membership(membership_id).status is MembershipStatus.EXPIRED

        service.renew_membership(membership_id, app_catalog["monthly_id"])
        assert service.get_membership(membership_id).status is MembershipStatus.ACTIVE

    def test_acepta_una_fecha_explicita(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        elegida = date.today() + timedelta(days=90)
        service.renew_membership(membership_id, app_catalog["biweekly_id"], start=elegida)

        periodos = sorted(service.get_membership(membership_id).periods, key=lambda p: p.start_date)
        assert periodos[-1].start_date.date() == elegida
        assert periodos[-1].end_date.date() == elegida + timedelta(days=14)

    def test_suma_el_total_pagado(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        service.renew_membership(membership_id, app_catalog["biweekly_id"])

        assert service.get_membership(membership_id).total_paid_cents == 65000

    def test_membresia_inexistente(self, app_db, app_catalog):
        with pytest.raises(NotFoundError):
            service.renew_membership(999, app_catalog["monthly_id"])


class TestEditarPeriodo:
    def test_recalcula_el_vencimiento(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        periodo = service.get_membership(membership_id).periods[0]

        service.update_period(periodo.id, app_catalog["biweekly_id"], date(2025, 3, 1), 25000)

        actualizado = service.get_membership(membership_id).periods[0]
        assert actualizado.start_date.date() == date(2025, 3, 1)
        assert actualizado.end_date.date() == date(2025, 3, 15)
        assert actualizado.price_paid_cents == 25000

    def test_rechaza_precio_negativo(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        periodo = service.get_membership(membership_id).periods[0]

        with pytest.raises(ValidationError):
            service.update_period(periodo.id, app_catalog["monthly_id"], date.today(), -100)

    def test_periodo_inexistente(self, app_db, app_catalog):
        with pytest.raises(NotFoundError):
            service.update_period(999, app_catalog["monthly_id"], date.today(), 100)


class TestBorrarPeriodo:
    def test_no_permite_borrar_el_unico_periodo(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        periodo = service.get_membership(membership_id).periods[0]

        with pytest.raises(ServiceError, match="único periodo"):
            service.delete_period(periodo.id)

    def test_borra_un_periodo_cuando_hay_varios(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        period_id = service.renew_membership(membership_id, app_catalog["monthly_id"])

        service.delete_period(period_id)
        assert len(service.get_membership(membership_id).periods) == 1


class TestListadoYEstadisticas:
    def _poblar(self, app_catalog):
        activo = alta("Activo Ramirez")
        vencido = alta("Vencido Torres")
        service.create_membership(activo, app_catalog["monthly_id"])
        service.create_membership(vencido, app_catalog["monthly_id"], start=date(2020, 1, 1))

    def test_lista_todas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_memberships()
        assert total == 2 and len(rows) == 2

    def test_filtra_por_activas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_memberships(status=MembershipStatus.ACTIVE)
        assert total == 1
        assert rows[0].member.name == "Activo Ramirez"

    def test_filtra_por_vencidas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_memberships(status=MembershipStatus.EXPIRED)
        assert total == 1
        assert rows[0].member.name == "Vencido Torres"

    def test_busca_por_nombre_del_socio(self, app_db, app_catalog):
        self._poblar(app_catalog)
        rows, total = service.list_memberships(search="ramirez")
        assert total == 1 and rows[0].member.name == "Activo Ramirez"

    def test_estadisticas(self, app_db, app_catalog):
        self._poblar(app_catalog)
        stats = service.membership_stats()
        assert (stats.total, stats.active, stats.expired) == (2, 1, 1)

    def test_autocompletado_de_socios(self, app_db):
        alta("Ana Lopez")
        alta("Beto Ruiz")

        assert len(service.search_members("ana")) == 1
        assert service.search_members("") == []

    def test_borra_una_membresia_con_sus_periodos(self, app_db, app_catalog):
        member_id = alta()
        membership_id = service.create_membership(member_id, app_catalog["monthly_id"])
        service.delete_membership(membership_id)

        with pytest.raises(NotFoundError):
            service.get_membership(membership_id)


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

    def test_no_borra_una_categoria_en_uso(self, app_db, app_catalog):
        service.create_membership(alta(), app_catalog["monthly_id"])
        with pytest.raises(ServiceError, match="membresías registradas"):
            service.delete_plan_category(app_catalog["category_id"])

    def test_borra_una_categoria_sin_uso(self, app_db):
        category_id = service.create_plan_category("Temporal")
        service.delete_plan_category(category_id)
        assert all(t.id != category_id for t in service.list_plan_categories())

    def test_crea_un_plan(self, app_db, app_catalog):
        service.create_plan(app_catalog["category_id"], "Trimestral", 3, DurationUnit.MONTH, 100000)
        assert len(service.list_plans()) == 3

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
        """El periodo guarda lo que el socio pago, no el precio de hoy."""
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])

        service.update_plan(app_catalog["monthly_id"], "Mensual", 1, DurationUnit.MONTH, 90000)

        periodo = service.get_membership(membership_id).periods[0]
        assert periodo.price_paid_cents == 40000

    def test_no_borra_un_plan_usado(self, app_db, app_catalog):
        service.create_membership(alta(), app_catalog["monthly_id"])
        with pytest.raises(ServiceError, match="periodos ya registrados"):
            service.delete_plan(app_catalog["monthly_id"])

    def test_borra_un_plan_sin_uso(self, app_db, app_catalog):
        plan_id = service.create_plan(
            app_catalog["category_id"], "Anual", 12, DurationUnit.MONTH, 400000
        )
        service.delete_plan(plan_id)
        assert all(d.id != plan_id for d in service.list_plans())


class TestEstadoDePeriodos:
    def test_periodo_futuro_esta_en_curso(self, app_db, app_catalog):
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"])
        periodo = service.get_membership(membership_id).periods[0]
        assert periodo.status is PeriodStatus.IN_PROGRESS

    def test_periodo_pasado_esta_completado(self, app_db, app_catalog):
        membership_id = service.create_membership(
            alta(), app_catalog["monthly_id"], start=date(2020, 1, 1)
        )
        periodo = service.get_membership(membership_id).periods[0]
        assert periodo.status is PeriodStatus.COMPLETED

    def test_periodo_que_vence_hoy_sigue_en_curso(self, app_db, app_catalog):
        inicio = date.today() - timedelta(days=30)
        membership_id = service.create_membership(alta(), app_catalog["monthly_id"], start=inicio)
        periodo = service.get_membership(membership_id).periods[0]

        if periodo.end_date.date() == date.today():
            assert periodo.status is PeriodStatus.IN_PROGRESS
            assert periodo.end_date > datetime.now()
