from decimal import Decimal

import pytest

from gym.domain.money import format_money, to_cents, to_pesos


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("400", 40000),
        ("400.50", 40050),
        ("0.01", 1),
        ("1,250.50", 125050),
        ("$350", 35000),
        (Decimal("99.99"), 9999),
        (250, 25000),
    ],
)
def test_convierte_pesos_a_centavos(entrada, esperado):
    assert to_cents(entrada) == esperado


def test_redondea_al_centavo_mas_cercano():
    assert to_cents("10.005") == 1001
    assert to_cents("10.004") == 1000


def test_rechaza_importes_invalidos():
    with pytest.raises(ValueError):
        to_cents("abc")


def test_convierte_centavos_a_pesos():
    assert to_pesos(125050) == Decimal("1250.50")


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (0, "$0.00"),
        (4000, "$40.00"),
        (125050, "$1,250.50"),
        (-4000, "-$40.00"),
    ],
)
def test_formatea_moneda_mexicana(centavos, esperado):
    assert format_money(centavos) == esperado


def test_sumar_precios_en_centavos_no_pierde_exactitud():
    """El caso que justifica usar enteros: 0.1 + 0.2 no da 0.3 en flotante."""
    total = sum(to_cents("0.1") for _ in range(3))
    assert total == 30
    assert format_money(total) == "$0.30"
