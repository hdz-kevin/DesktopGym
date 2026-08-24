"""Los estados se derivan de fechas y deben coincidir en Python y en SQL.

Si `hybrid_property` y su expresion SQL divergieran, un socio podria aparecer
activo en la tabla y vencido en su perfil.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from gym.data.models import Member, Membership, Period
from gym.domain.enums import MembershipStatus, MemberStatus, PeriodStatus


def _member(session, nombre: str, code: str) -> Member:
    member = Member(name=nombre, code=code, gender="male")
    session.add(member)
    session.flush()
    return member


def _membership_con_periodo(session, member, duration, inicio, fin) -> Membership:
    membership = Membership(member_id=member.id, membership_type_id=duration.membership_type_id)
    session.add(membership)
    session.flush()
    session.add(
        Period(
            membership_id=membership.id,
            duration_id=duration.id,
            start_date=inicio,
            end_date=fin,
            price_paid_cents=duration.price_cents,
        )
    )
    session.commit()
    session.refresh(membership)
    return membership


@pytest.fixture
def ahora() -> datetime:
    return datetime.now()


class TestPeriodStatus:
    def test_vigente_en_python(self, session, catalog, ahora):
        member = _member(session, "Vigente", "10001")
        m = _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=5),
            ahora + timedelta(days=25),
        )
        assert m.periods[0].status is PeriodStatus.IN_PROGRESS

    def test_vencido_en_python(self, session, catalog, ahora):
        member = _member(session, "Vencido", "10002")
        m = _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=40),
            ahora - timedelta(days=10),
        )
        assert m.periods[0].status is PeriodStatus.COMPLETED

    def test_filtro_en_sql_coincide_con_python(self, session, catalog, ahora):
        vigente = _member(session, "Vigente", "10003")
        vencido = _member(session, "Vencido", "10004")
        _membership_con_periodo(
            session,
            vigente,
            catalog["monthly"],
            ahora - timedelta(days=5),
            ahora + timedelta(days=25),
        )
        _membership_con_periodo(
            session,
            vencido,
            catalog["monthly"],
            ahora - timedelta(days=40),
            ahora - timedelta(days=10),
        )

        en_curso = session.scalars(
            select(Period).where(Period.status == PeriodStatus.IN_PROGRESS.value)
        ).all()

        assert len(en_curso) == 1
        assert en_curso[0].status is PeriodStatus.IN_PROGRESS
        assert en_curso[0].membership.member.name == "Vigente"


class TestMembershipStatus:
    def test_activa_si_algun_periodo_esta_en_curso(self, session, catalog, ahora):
        member = _member(session, "Socio", "10005")
        membership = _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        session.add(
            Period(
                membership_id=membership.id,
                duration_id=catalog["monthly"].id,
                start_date=ahora - timedelta(days=5),
                end_date=ahora + timedelta(days=25),
                price_paid_cents=40000,
            )
        )
        session.commit()
        session.refresh(membership)

        assert membership.status is MembershipStatus.ACTIVE

    def test_vencida_si_todos_los_periodos_terminaron(self, session, catalog, ahora):
        member = _member(session, "Socio", "10006")
        membership = _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        assert membership.status is MembershipStatus.EXPIRED

    def test_sin_periodos_es_vencida(self, session, catalog):
        member = _member(session, "Socio", "10007")
        membership = Membership(member_id=member.id, membership_type_id=catalog["type"].id)
        session.add(membership)
        session.commit()
        assert membership.status is MembershipStatus.EXPIRED

    def test_filtro_en_sql_coincide_con_python(self, session, catalog, ahora):
        activo = _member(session, "Activo", "10008")
        vencido = _member(session, "Vencido", "10009")
        _membership_con_periodo(
            session,
            activo,
            catalog["monthly"],
            ahora - timedelta(days=5),
            ahora + timedelta(days=25),
        )
        _membership_con_periodo(
            session,
            vencido,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )

        activas = session.scalars(
            select(Membership).where(Membership.status == MembershipStatus.ACTIVE.value)
        ).all()

        assert len(activas) == 1
        assert activas[0].status is MembershipStatus.ACTIVE
        assert activas[0].member.name == "Activo"


class TestMemberStatus:
    def test_sin_membresias(self, session):
        member = _member(session, "Nuevo", "10010")
        session.commit()
        assert member.status is MemberStatus.NO_MEMBERSHIP

    def test_activo_con_una_membresia_vigente(self, session, catalog, ahora):
        member = _member(session, "Activo", "10011")
        _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=5),
            ahora + timedelta(days=25),
        )
        session.refresh(member)
        assert member.status is MemberStatus.ACTIVE
        assert member.active_membership() is not None

    def test_vencido_con_todas_las_membresias_terminadas(self, session, catalog, ahora):
        member = _member(session, "Vencido", "10012")
        _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        session.refresh(member)
        assert member.status is MemberStatus.EXPIRED
        assert member.active_membership() is None

    def test_latest_membership_devuelve_la_mas_reciente(self, session, catalog, ahora):
        member = _member(session, "Socio", "10013")
        _membership_con_periodo(
            session,
            member,
            catalog["monthly"],
            ahora - timedelta(days=70),
            ahora - timedelta(days=40),
        )
        reciente = _membership_con_periodo(
            session,
            member,
            catalog["biweekly"],
            ahora - timedelta(days=2),
            ahora + timedelta(days=12),
        )
        session.refresh(member)
        assert member.latest_membership().id == reciente.id
