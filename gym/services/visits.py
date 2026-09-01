"""Visitas sueltas: quien paga por entrada sin ser socio."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import func, select

from gym.data.database import session_scope
from gym.data.models import Visit
from gym.domain.dates import day_bounds, month_bounds, week_bounds
from gym.services.errors import ValidationError

logger = logging.getLogger(__name__)


class VisitRange(str, Enum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"

    def label(self) -> str:
        return {
            VisitRange.TODAY: "Hoy",
            VisitRange.WEEK: "Esta semana",
            VisitRange.MONTH: "Este mes",
            VisitRange.ALL: "Todas",
        }[self]


@dataclass
class VisitTotals:
    count: int = 0
    revenue_cents: int = 0


def _bounds(range_: VisitRange, moment: date | None = None):
    moment = moment or date.today()
    if range_ is VisitRange.TODAY:
        return day_bounds(moment)
    if range_ is VisitRange.WEEK:
        return week_bounds(moment)
    if range_ is VisitRange.MONTH:
        return month_bounds(moment)
    return None


def _apply_range(statement, range_: VisitRange, moment: date | None = None):
    bounds = _bounds(range_, moment)
    if bounds is None:
        return statement
    start, end = bounds
    return statement.where(Visit.visit_at >= start, Visit.visit_at <= end)


def create_visit(price_cents: int, visit_at: datetime | None = None) -> int:
    if price_cents < 0:
        raise ValidationError({"price": "El precio no puede ser negativo."})

    with session_scope() as session:
        visit = Visit(price_cents=price_cents, visit_at=visit_at or datetime.now())
        session.add(visit)
        session.flush()
        logger.info("Visita registrada por %s centavos", price_cents)
        return visit.id


def list_visits(
    range_: VisitRange = VisitRange.TODAY, offset: int = 0, limit: int = 25
) -> tuple[list[Visit], int]:
    with session_scope() as session:
        total = session.scalar(_apply_range(select(func.count()).select_from(Visit), range_))
        rows = session.scalars(
            _apply_range(select(Visit), range_)
            .order_by(Visit.visit_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), int(total or 0)


def totals(range_: VisitRange, moment: date | None = None) -> VisitTotals:
    """Cuenta y suma en una sola consulta agregada."""
    with session_scope() as session:
        count, revenue = session.execute(
            _apply_range(
                select(func.count(Visit.id), func.coalesce(func.sum(Visit.price_cents), 0)),
                range_,
                moment,
            )
        ).one()
        return VisitTotals(count=int(count or 0), revenue_cents=int(revenue or 0))
