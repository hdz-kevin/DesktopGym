"""Ventas de la tienda: carrito y cobro."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from gym.data.database import session_scope
from gym.data.models import Product, ProductSale, Sale
from gym.domain.dates import day_bounds, month_bounds, week_bounds
from gym.services.errors import (
    InsufficientStockError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from gym.services.visits import VisitRange

logger = logging.getLogger(__name__)


@dataclass
class CartLine:
    product_id: int
    name: str
    unit_price_cents: int
    quantity: int
    stock: int

    @property
    def subtotal_cents(self) -> int:
        return self.unit_price_cents * self.quantity


@dataclass
class Cart:
    """Carrito en memoria. No toca la base hasta el cobro."""

    lines: dict[int, CartLine] = field(default_factory=dict)

    @property
    def total_cents(self) -> int:
        return sum(line.subtotal_cents for line in self.lines.values())

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines.values())

    @property
    def is_empty(self) -> bool:
        return not self.lines

    def ordered_lines(self) -> list[CartLine]:
        return sorted(self.lines.values(), key=lambda line: line.name)

    def add(self, product: Product, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValidationError({"quantity": "La cantidad debe ser mayor a cero."})

        line = self.lines.get(product.id)
        actual = (line.quantity if line else 0) + quantity

        if actual > product.stock:
            raise InsufficientStockError(product.name, product.stock)

        if line is None:
            self.lines[product.id] = CartLine(
                product_id=product.id,
                name=product.name,
                unit_price_cents=product.price_cents,
                quantity=quantity,
                stock=product.stock,
            )
        else:
            line.quantity = actual

    def set_quantity(self, product_id: int, quantity: int) -> None:
        line = self.lines.get(product_id)
        if line is None:
            return
        if quantity <= 0:
            del self.lines[product_id]
            return
        if quantity > line.stock:
            raise InsufficientStockError(line.name, line.stock)
        line.quantity = quantity

    def remove(self, product_id: int) -> None:
        self.lines.pop(product_id, None)

    def clear(self) -> None:
        self.lines.clear()


def checkout(cart: Cart, sold_at: datetime | None = None) -> int:
    """Cobra el carrito en una sola transaccion.

    El stock se vuelve a leer aqui dentro, no se confia en el que se mostro al
    armar el carrito: entre que el cajero agrego el producto y cobro, alguien
    pudo haber ajustado el inventario. Si algo falla, la transaccion completa se
    revierte y no queda una venta a medias.
    """
    if cart.is_empty:
        raise ServiceError("El carrito está vacío.")

    with session_scope() as session:
        sale = Sale(total_cents=0, sold_at=sold_at or datetime.now())
        session.add(sale)
        session.flush()

        total = 0
        for line in cart.ordered_lines():
            product = session.get(Product, line.product_id)
            if product is None:
                raise NotFoundError(f'El producto "{line.name}" ya no existe.')

            if product.stock < line.quantity:
                raise InsufficientStockError(product.name, product.stock)
            product.stock -= line.quantity

            subtotal = product.price_cents * line.quantity
            total += subtotal

            # Se copian nombre y precio: si manana cambian, el ticket de hoy
            # debe seguir diciendo lo que realmente se cobro.
            session.add(
                ProductSale(
                    sale_id=sale.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_price_cents=product.price_cents,
                    quantity=line.quantity,
                    subtotal_cents=subtotal,
                )
            )

        sale.total_cents = total
        logger.info("Venta %s cobrada por %s centavos", sale.id, total)
        return sale.id


def _apply_range(statement, range_: VisitRange, moment: date | None = None):
    moment = moment or date.today()
    bounds = None
    if range_ is VisitRange.TODAY:
        bounds = day_bounds(moment)
    elif range_ is VisitRange.WEEK:
        bounds = week_bounds(moment)
    elif range_ is VisitRange.MONTH:
        bounds = month_bounds(moment)

    if bounds is None:
        return statement
    start, end = bounds
    return statement.where(Sale.sold_at >= start, Sale.sold_at <= end)


def list_sales(
    range_: VisitRange = VisitRange.TODAY, offset: int = 0, limit: int = 25
) -> tuple[list[Sale], int]:
    with session_scope() as session:
        total = session.scalar(_apply_range(select(func.count()).select_from(Sale), range_))
        rows = session.scalars(
            _apply_range(select(Sale), range_)
            .options(selectinload(Sale.lines))
            .order_by(Sale.sold_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), int(total or 0)


def get_sale(sale_id: int) -> Sale:
    with session_scope() as session:
        sale = session.scalar(
            select(Sale).where(Sale.id == sale_id).options(selectinload(Sale.lines))
        )
        if sale is None:
            raise NotFoundError("La venta ya no existe.")
        return sale


@dataclass
class SalesTotals:
    count: int = 0
    revenue_cents: int = 0
    items: int = 0


def totals(range_: VisitRange, moment: date | None = None) -> SalesTotals:
    with session_scope() as session:
        count, revenue = session.execute(
            _apply_range(
                select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_cents), 0)),
                range_,
                moment,
            )
        ).one()

        items = session.scalar(
            _apply_range(
                select(func.coalesce(func.sum(ProductSale.quantity), 0)).join(
                    Sale, ProductSale.sale_id == Sale.id
                ),
                range_,
                moment,
            )
        )
        return SalesTotals(
            count=int(count or 0),
            revenue_cents=int(revenue or 0),
            items=int(items or 0),
        )


def top_products(range_: VisitRange, limit: int = 5) -> list[tuple[str, int, int]]:
    """Productos mas vendidos: nombre, piezas e importe."""
    with session_scope() as session:
        rows = session.execute(
            _apply_range(
                select(
                    ProductSale.product_name,
                    func.sum(ProductSale.quantity),
                    func.sum(ProductSale.subtotal_cents),
                ).join(Sale, ProductSale.sale_id == Sale.id),
                range_,
            )
            .group_by(ProductSale.product_name)
            .order_by(func.sum(ProductSale.quantity).desc())
            .limit(limit)
        ).all()
        return [(name, int(qty), int(amount)) for name, qty, amount in rows]
