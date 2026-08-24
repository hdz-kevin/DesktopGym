from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from gym.data.database import session_scope
from gym.data.models import Membership, Period
from gym.domain.enums import MemberGender
from gym.services import members as members_service
from gym.services.checkin import verify_code


def alta(nombre: str = "Ana Lopez") -> tuple[int, str]:
    member_id = members_service.create_member(
        members_service.MemberForm(name=nombre, gender=MemberGender.FEMALE)
    )
    return member_id, members_service.get_member(member_id).code


def dar_periodo(member_id: int, catalog: dict, dias_restantes: int) -> None:
    ahora = datetime.now()
    with session_scope() as session:
        membership = Membership(member_id=member_id, membership_type_id=catalog["type_id"])
        session.add(membership)
        session.flush()
        session.add(
            Period(
                membership_id=membership.id,
                duration_id=catalog["monthly_id"],
                start_date=ahora - timedelta(days=30),
                end_date=ahora + timedelta(days=dias_restantes),
                price_paid_cents=40000,
            )
        )


class TestCodigoInvalido:
    @pytest.mark.parametrize("codigo", ["", "123", "123456", "abcde", "12a45", "   "])
    def test_rechaza_formato_incorrecto(self, app_db, codigo):
        resultado = verify_code(codigo)
        assert not resultado.granted
        assert "5 dígitos" in resultado.message

    def test_codigo_no_registrado(self, app_db):
        resultado = verify_code("99999")
        assert not resultado.granted
        assert "No encontramos" in resultado.message
        assert resultado.member is None


class TestAccesoConcedido:
    def test_membresia_vigente(self, app_db, app_catalog):
        member_id, codigo = alta()
        dar_periodo(member_id, app_catalog, dias_restantes=12)

        resultado = verify_code(codigo)

        assert resultado.granted
        assert resultado.message == "¡Bienvenido!"
        assert resultado.member_name == "Ana Lopez"
        assert "Vence en" in resultado.detail

    def test_ultimo_dia_todavia_da_acceso(self, app_db, app_catalog):
        """El periodo cierra al final del dia, no a medianoche del ultimo dia."""
        member_id, codigo = alta()
        ahora = datetime.now()
        with session_scope() as session:
            membership = Membership(member_id=member_id, membership_type_id=app_catalog["type_id"])
            session.add(membership)
            session.flush()
            session.add(
                Period(
                    membership_id=membership.id,
                    duration_id=app_catalog["monthly_id"],
                    start_date=ahora - timedelta(days=30),
                    end_date=ahora.replace(hour=23, minute=59, second=59),
                    price_paid_cents=40000,
                )
            )

        assert verify_code(codigo).granted

    def test_ignora_espacios_al_teclear(self, app_db, app_catalog):
        member_id, codigo = alta()
        dar_periodo(member_id, app_catalog, dias_restantes=5)
        assert verify_code(f" {codigo} ").granted


class TestAccesoDenegado:
    def test_socio_sin_membresia(self, app_db):
        _, codigo = alta()
        resultado = verify_code(codigo)

        assert not resultado.granted
        assert "no tiene ninguna membresía" in resultado.message
        assert resultado.member is not None

    def test_membresia_vencida_indica_la_fecha(self, app_db, app_catalog):
        member_id, codigo = alta()
        dar_periodo(member_id, app_catalog, dias_restantes=-3)

        resultado = verify_code(codigo)

        assert not resultado.granted
        assert resultado.message == "Membresía vencida."
        assert "Venció el" in resultado.detail

    def test_renovar_reactiva_el_acceso(self, app_db, app_catalog):
        member_id, codigo = alta()
        dar_periodo(member_id, app_catalog, dias_restantes=-3)
        assert not verify_code(codigo).granted

        dar_periodo(member_id, app_catalog, dias_restantes=27)
        assert verify_code(codigo).granted
