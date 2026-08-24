"""Corte de caja: cuanto entro y por que concepto.

Todo se calcula con consultas agregadas en SQL en vez de traer los registros a
Python, para que el corte del mes siga siendo instantaneo con anos de historia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, and_, exists, func, select

from gym.data.database import session_scope
from gym.data.models import Period, Sale, Visit
from gym.domain.dates import day_bounds, month_bounds, week_bounds
from gym.services.visits import VisitRange


@dataclass
class ConceptTotal:
    count: int = 0
    revenue_cents: int = 0


@dataclass
class CashReport:
    range_: VisitRange
    visits: ConceptTotal
    sales: ConceptTotal
    new_memberships: ConceptTotal
    renewals: ConceptTotal

    @property
    def memberships_revenue_cents(self) -> int:
        return self.new_memberships.revenue_cents + self.renewals.revenue_cents

    @property
    def total_revenue_cents(self) -> int:
        return self.visits.revenue_cents + self.sales.revenue_cents + self.memberships_revenue_cents

    @property
    def transaction_count(self) -> int:
        return (
            self.visits.count + self.sales.count + self.new_memberships.count + self.renewals.count
        )


def range_bounds(
    range_: VisitRange, moment: date | None = None
) -> tuple[datetime, datetime] | None:
    moment = moment or date.today()
    if range_ is VisitRange.TODAY:
        return day_bounds(moment)
    if range_ is VisitRange.WEEK:
        return week_bounds(moment)
    if range_ is VisitRange.MONTH:
        return month_bounds(moment)
    return None


def _between(statement: Select, column, range_: VisitRange, moment: date | None):
    bounds = range_bounds(range_, moment)
    if bounds is None:
        return statement
    start, end = bounds
    return statement.where(column >= start, column <= end)


def _is_renewal():
    """Un periodo es renovacion si su membresia ya tenia otro periodo anterior.

    Es la unica forma de distinguir un alta nueva de una renovacion sin guardar
    una bandera que se podria desincronizar al corregir un periodo.
    """
    previous = Period.__table__.alias("previo")
    return exists(
        select(previous.c.id).where(
            and_(
                previous.c.membership_id == Period.membership_id,
                previous.c.start_date < Period.start_date,
            )
        )
    )


def _concept_from_periods(session, range_: VisitRange, moment: date | None, renewals: bool):
    condition = _is_renewal() if renewals else ~_is_renewal()
    statement = _between(
        select(
            func.count(Period.id),
            func.coalesce(func.sum(Period.price_paid_cents), 0),
        ).where(condition),
        Period.created_at,
        range_,
        moment,
    )
    count, revenue = session.execute(statement).one()
    return ConceptTotal(count=int(count or 0), revenue_cents=int(revenue or 0))


def build_report(range_: VisitRange, moment: date | None = None) -> CashReport:
    with session_scope() as session:
        visit_count, visit_revenue = session.execute(
            _between(
                select(
                    func.count(Visit.id),
                    func.coalesce(func.sum(Visit.price_cents), 0),
                ),
                Visit.visit_at,
                range_,
                moment,
            )
        ).one()

        sale_count, sale_revenue = session.execute(
            _between(
                select(
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_cents), 0),
                ),
                Sale.sold_at,
                range_,
                moment,
            )
        ).one()

        return CashReport(
            range_=range_,
            visits=ConceptTotal(int(visit_count or 0), int(visit_revenue or 0)),
            sales=ConceptTotal(int(sale_count or 0), int(sale_revenue or 0)),
            new_memberships=_concept_from_periods(session, range_, moment, renewals=False),
            renewals=_concept_from_periods(session, range_, moment, renewals=True),
        )


def daily_breakdown(range_: VisitRange, moment: date | None = None) -> list[tuple[str, int]]:
    """Ingresos por dia dentro del periodo, para ver la tendencia."""
    bounds = range_bounds(range_, moment)
    if bounds is None:
        return []
    start, end = bounds

    with session_scope() as session:
        rows: dict[str, int] = {}
        sources = [
            (Visit.visit_at, Visit.price_cents, Visit.id),
            (Sale.sold_at, Sale.total_cents, Sale.id),
            (Period.created_at, Period.price_paid_cents, Period.id),
        ]
        for column, amount, _ in sources:
            for day, total in session.execute(
                select(func.date(column), func.coalesce(func.sum(amount), 0))
                .where(column >= start, column <= end)
                .group_by(func.date(column))
            ).all():
                rows[day] = rows.get(day, 0) + int(total or 0)

        return sorted(rows.items())
