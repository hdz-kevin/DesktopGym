from datetime import datetime

import pytest

from gym.domain.enums import DurationUnit
from gym.domain.rules import generate_member_code, initials, line_subtotal_cents, period_end_date


class TestPeriodEndDate:
    def test_dias(self):
        end = period_end_date(datetime(2025, 1, 10), DurationUnit.DAY, 15)
        assert end.date() == datetime(2025, 1, 25).date()

    def test_semanas(self):
        end = period_end_date(datetime(2025, 1, 10), DurationUnit.WEEK, 2)
        assert end.date() == datetime(2025, 1, 24).date()

    def test_meses(self):
        end = period_end_date(datetime(2025, 1, 10), DurationUnit.MONTH, 1)
        assert end.date() == datetime(2025, 2, 10).date()

    def test_cierra_al_final_del_dia(self):
        """El socio conserva el ultimo dia completo, no vence a medianoche."""
        end = period_end_date(datetime(2025, 1, 10, 14, 30), DurationUnit.DAY, 1)
        assert (end.hour, end.minute, end.second) == (23, 59, 59)

    def test_ignora_la_hora_de_inicio(self):
        manana = period_end_date(datetime(2025, 1, 10, 8, 0), DurationUnit.MONTH, 1)
        noche = period_end_date(datetime(2025, 1, 10, 22, 0), DurationUnit.MONTH, 1)
        assert manana == noche

    def test_fin_de_mes_no_desborda(self):
        """31 de enero mas un mes vence el 28 de febrero, no el 3 de marzo."""
        end = period_end_date(datetime(2025, 1, 31), DurationUnit.MONTH, 1)
        assert end.date() == datetime(2025, 2, 28).date()

    def test_fin_de_mes_en_ano_bisiesto(self):
        end = period_end_date(datetime(2024, 1, 31), DurationUnit.MONTH, 1)
        assert end.date() == datetime(2024, 2, 29).date()

    def test_cruza_el_ano(self):
        end = period_end_date(datetime(2025, 11, 15), DurationUnit.MONTH, 3)
        assert end.date() == datetime(2026, 2, 15).date()

    def test_rechaza_duracion_no_positiva(self):
        with pytest.raises(ValueError):
            period_end_date(datetime(2025, 1, 10), DurationUnit.MONTH, 0)


class TestMemberCode:
    def test_genera_codigo_de_cinco_digitos(self):
        code = generate_member_code(lambda _: False)
        assert len(code) == 5
        assert code.isdigit()

    def test_reintenta_hasta_encontrar_uno_libre(self):
        ocupados = set()
        primero = generate_member_code(lambda c: c in ocupados)
        ocupados.add(primero)
        segundo = generate_member_code(lambda c: c in ocupados)
        assert segundo != primero

    def test_falla_si_todos_estan_ocupados(self):
        with pytest.raises(RuntimeError):
            generate_member_code(lambda _: True)


class TestInitials:
    @pytest.mark.parametrize(
        ("nombre", "esperado"),
        [
            ("Juan Perez", "JP"),
            ("Ana", "A"),
            ("Maria Fernanda Lopez Garcia", "MF"),
            ("  luis   ramos  ", "LR"),
        ],
    )
    def test_toma_las_dos_primeras_palabras(self, nombre, esperado):
        assert initials(nombre) == esperado


class TestLineSubtotal:
    def test_multiplica_precio_por_cantidad(self):
        assert line_subtotal_cents(2500, 3) == 7500

    def test_rechaza_cantidad_menor_a_uno(self):
        with pytest.raises(ValueError):
            line_subtotal_cents(2500, 0)
