"""Manejo de dinero en centavos.

Todo importe se almacena como entero de centavos. Los flotantes no son exactos
en base dos, asi que sumar precios con ellos produce descuadres de centavos en
el corte de caja.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def to_cents(amount: str | int | float | Decimal) -> int:
    """Convierte un importe en pesos a centavos, redondeando al centavo mas cercano."""
    if isinstance(amount, int):
        return amount * 100
    try:
        value = Decimal(str(amount).strip().replace(",", "").replace("$", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Importe invalido: {amount!r}") from exc
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_pesos(cents: int) -> Decimal:
    """Convierte centavos a un Decimal exacto en pesos."""
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def format_money(cents: int) -> str:
    """Formatea centavos como moneda mexicana: 125050 -> '$1,250.50'."""
    sign = "-" if cents < 0 else ""
    pesos = to_pesos(abs(cents))
    return f"{sign}${pesos:,.2f}"
