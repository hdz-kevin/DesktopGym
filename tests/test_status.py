"""Los estados se derivan de fechas y deben coincidir en Python y en SQL.

Si `hybrid_property` y su expresion SQL divergieran, un socio podria aparecer
activo en la tabla y vencido en su perfil.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from gym.data.models import Member, Payment
from gym.domain.enums import MemberStatus


def _member(session, nombre: str, code: str, category) -> Member:
    member = Member(name=nombre, code=code, plan_category_id=category.id)
    session.add(member)
    session.flush()
    return member


def _pago(session, member, plan, inicio, fin) -> Payment:
    payment = Payment(
        member_id=member.id,
        plan_id=plan.id,
        start_date=inicio,
        end_date=fin,
        price_paid_cents=plan.price_cents,
    )
    session.add(payment)
    session.commit()
    session.refresh(member)
    return payment


@pytest.fixture
def ahora() -> datetime:
    return datetime.now()


class TestMemberStatus:
    def test_sin_pagos_es_vencido(self, session, catalog):
        member = _member(session, "Nuevo", "10010", catalog["category"])
        session.commit()
        assert member.status is MemberStatus.EXPIRED

    def test_activo_si_algun_pago_sigue_vigente(self, session, catalog, ahora):
        member = _member(session, "Activo", "10011", catalog["category"])
        _pago(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        session.add(
            Payment(
                member_id=member.id,
                plan_id=catalog["monthly"].id,
                start_date=ahora - timedelta(days=5),
                end_date=ahora + timedelta(days=25),
                price_paid_cents=40000,
            )
        )
        session.commit()
        session.refresh(member)
        assert member.status is MemberStatus.ACTIVE

    def test_vencido_si_todos_los_pagos_terminaron(self, session, catalog, ahora):
        member = _member(session, "Vencido", "10012", catalog["category"])
        _pago(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        assert member.status is MemberStatus.EXPIRED

    def test_filtro_en_sql_coincide_con_python(self, session, catalog, ahora):
        activo = _member(session, "Activo", "10008", catalog["category"])
        vencido = _member(session, "Vencido", "10009", catalog["category"])
        _pago(
            session,
            activo,
            catalog["monthly"],
            ahora - timedelta(days=5),
            ahora + timedelta(days=25),
        )
        _pago(
            session,
            vencido,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )

        activos = session.scalars(
            select(Member).where(Member.status == MemberStatus.ACTIVE.value)
        ).all()

        assert len(activos) == 1
        assert activos[0].status is MemberStatus.ACTIVE
        assert activos[0].name == "Activo"

    def test_recent_payment_es_el_de_id_mas_alto(self, session, catalog, ahora):
        member = _member(session, "Socio", "10013", catalog["category"])
        _pago(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        reciente = _pago(
            session,
            member,
            catalog["biweekly"],
            ahora - timedelta(days=2),
            ahora + timedelta(days=12),
        )
        session.refresh(member)
        assert member.recent_payment is not None
        assert member.recent_payment.id == reciente.id
