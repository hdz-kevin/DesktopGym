from datetime import date, datetime

import pytest

from gym.domain.dates import (
    add_months,
    age_from,
    day_bounds,
    end_of_day,
    format_date,
    format_datetime,
    format_range,
    humanize_delta,
    month_bounds,
    start_of_day,
    week_bounds,
)


def test_start_y_end_of_day():
    momento = datetime(2025, 3, 5, 14, 22, 9)
    assert start_of_day(momento) == datetime(2025, 3, 5, 0, 0, 0)
    assert end_of_day(momento).hour == 23
    assert end_of_day(momento).minute == 59


@pytest.mark.parametrize(
    ("inicio", "meses", "esperado"),
    [
        (datetime(2025, 1, 15), 1, datetime(2025, 2, 15)),
        (datetime(2025, 1, 31), 1, datetime(2025, 2, 28)),
        (datetime(2025, 12, 15), 1, datetime(2026, 1, 15)),
        (datetime(2025, 3, 31), 2, datetime(2025, 5, 31)),
        (datetime(2025, 5, 31), 1, datetime(2025, 6, 30)),
    ],
)
def test_add_months_recorta_al_ultimo_dia(inicio, meses, esperado):
    assert add_months(inicio, meses) == esperado


def test_formato_de_fecha_en_espanol():
    assert format_date(date(2025, 1, 5)) == "05 Ene 2025"
    assert format_date(date(2025, 12, 31)) == "31 Dic 2025"


def test_formato_de_fecha_y_hora():
    assert format_datetime(datetime(2025, 1, 5, 15, 45)) == "05 Ene 2025, 03:45 p.m."
    assert format_datetime(datetime(2025, 1, 5, 9, 5)) == "05 Ene 2025, 09:05 a.m."
    assert format_datetime(datetime(2025, 1, 5, 0, 30)) == "05 Ene 2025, 12:30 a.m."


def test_formato_de_rango():
    assert format_range(date(2025, 1, 5), date(2025, 2, 4)) == "05 Ene 2025 - 04 Feb 2025"


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (1, "1 día"),
        (3, "3 días"),
        (7, "1 semana"),
        (10, "1 semana 3 días"),
        (35, "1 mes 5 días"),
    ],
)
def test_humaniza_la_distancia(dias, esperado):
    from datetime import timedelta

    ahora = datetime(2025, 6, 1, 12, 0)
    assert humanize_delta(ahora + timedelta(days=dias), ahora) == esperado


def test_edad_a_partir_de_fecha_de_nacimiento():
    assert age_from(date(2000, 6, 15), date(2025, 6, 15)) == 25
    assert age_from(date(2000, 6, 16), date(2025, 6, 15)) == 24
    assert age_from(None) is None


def test_limites_de_dia_semana_y_mes():
    dia = date(2025, 3, 5)  # miercoles

    inicio, fin = day_bounds(dia)
    assert inicio.date() == dia and fin.date() == dia

    inicio, fin = week_bounds(dia)
    assert inicio.date() == date(2025, 3, 3)  # lunes
    assert fin.date() == date(2025, 3, 9)  # domingo

    inicio, fin = month_bounds(dia)
    assert inicio.date() == date(2025, 3, 1)
    assert fin.date() == date(2025, 3, 31)
