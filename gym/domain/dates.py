"""Utilidades de fecha con formato en espanol.

Se evita `locale` del sistema porque en Windows los nombres de mes en espanol no
estan garantizados; las tablas se definen aqui de forma explicita.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

MONTHS_SHORT = [
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]

MONTHS_LONG = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def start_of_day(moment: datetime | date) -> datetime:
    if isinstance(moment, datetime):
        return moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime(moment.year, moment.month, moment.day)


def end_of_day(moment: datetime | date) -> datetime:
    if isinstance(moment, datetime):
        return moment.replace(hour=23, minute=59, second=59, microsecond=999999)
    return datetime(moment.year, moment.month, moment.day, 23, 59, 59, 999999)


def add_months(moment: datetime, months: int) -> datetime:
    """Suma meses recortando al ultimo dia del mes destino.

    Un periodo que inicia el 31 de enero por un mes vence el 28 de febrero,
    no el 3 de marzo. La suma nativa de PHP y de Carbon desborda al mes siguiente,
    lo que dejaria al socio con dias de mas.
    """
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def format_date(moment: datetime | date) -> str:
    """'05 Ene 2025'."""
    return f"{moment.day:02d} {MONTHS_SHORT[moment.month - 1]} {moment.year}"


def format_datetime(moment: datetime) -> str:
    """'05 Ene 2025, 03:45 p.m.'."""
    hour = moment.hour % 12 or 12
    meridiem = "a.m." if moment.hour < 12 else "p.m."
    return f"{format_date(moment)}, {hour:02d}:{moment.minute:02d} {meridiem}"


def format_range(start: datetime | date, end: datetime | date) -> str:
    """'05 Ene 2025 - 04 Feb 2025'."""
    return f"{format_date(start)} - {format_date(end)}"


def humanize_delta(target: datetime, reference: datetime | None = None, parts: int = 2) -> str:
    """Distancia absoluta entre dos fechas: '1 mes 5 días'."""
    reference = reference or datetime.now()
    delta = abs(target - reference)
    days = delta.days
    units: list[tuple[int, str, str]] = []

    years, days = divmod(days, 365)
    if years:
        units.append((years, "año", "años"))
    months, days = divmod(days, 30)
    if months:
        units.append((months, "mes", "meses"))
    weeks, remaining_days = divmod(days, 7)
    if weeks:
        units.append((weeks, "semana", "semanas"))
    if remaining_days:
        units.append((remaining_days, "día", "días"))

    if not units:
        hours = delta.seconds // 3600
        if hours:
            units.append((hours, "hora", "horas"))
        else:
            minutes = max(1, delta.seconds // 60)
            units.append((minutes, "minuto", "minutos"))

    chosen = units[:parts]
    return " ".join(f"{n} {singular if n == 1 else plural}" for n, singular, plural in chosen)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    return start_of_day(day), end_of_day(day)


def week_bounds(day: date) -> tuple[datetime, datetime]:
    """Semana de lunes a domingo."""
    monday = day - timedelta(days=day.weekday())
    return start_of_day(monday), end_of_day(monday + timedelta(days=6))


def month_bounds(day: date) -> tuple[datetime, datetime]:
    first = day.replace(day=1)
    last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return start_of_day(first), end_of_day(last)
