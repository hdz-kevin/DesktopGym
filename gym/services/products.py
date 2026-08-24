"""Catalogo de productos de la tienda."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, or_, select

from gym.data.database import session_scope
from gym.data.models import Product, ProductSale
from gym.services.errors import NotFoundError, ServiceError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ProductForm:
    name: str
    price_cents: int
    stock: int | None = None
    is_active: bool = True

    @property
    def tracks_stock(self) -> bool:
        return self.stock is not None


def validate(form: ProductForm) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not form.name.strip():
        errors["name"] = "El nombre es obligatorio."
    elif len(form.name.strip()) > 255:
        errors["name"] = "El nombre es demasiado largo."
    if form.price_cents < 0:
        errors["price"] = "El precio no puede ser negativo."
    if form.stock is not None and form.stock < 0:
        errors["stock"] = "El stock no puede ser negativo."
    return errors


def create_product(form: ProductForm) -> int:
    errors = validate(form)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        product = Product(
            name=form.name.strip(),
            price_cents=form.price_cents,
            stock=form.stock,
            is_active=form.is_active,
        )
        session.add(product)
        session.flush()
        logger.info("Producto creado: %s", product.name)
        return product.id


def update_product(product_id: int, form: ProductForm) -> None:
    errors = validate(form)
    if errors:
        raise ValidationError(errors)

    with session_scope() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")

        product.name = form.name.strip()
        product.price_cents = form.price_cents
        product.stock = form.stock
        product.is_active = form.is_active


def delete_product(product_id: int) -> None:
    """Solo se borran productos que nunca se han vendido.

    Las lineas de venta guardan el nombre y el precio del momento, pero se
    apoyan en el producto para reportes; borrarlo dejaria ventas huerfanas.
    """
    with session_scope() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")

        sold = session.scalar(
            select(func.count())
            .select_from(ProductSale)
            .where(ProductSale.product_id == product_id)
        )
        if sold:
            raise ServiceError(
                "Este producto ya tiene ventas registradas. Desactívalo en lugar de eliminarlo."
            )
        session.delete(product)


def set_active(product_id: int, is_active: bool) -> None:
    with session_scope() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")
        product.is_active = is_active


def adjust_stock(product_id: int, delta: int) -> int:
    """Suma o resta piezas al inventario y devuelve el nuevo total."""
    with session_scope() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")
        if product.stock is None:
            raise ServiceError("Este producto no lleva control de inventario.")

        nuevo = product.stock + delta
        if nuevo < 0:
            raise ServiceError("El stock no puede quedar en negativo.")
        product.stock = nuevo
        return nuevo


def _apply_filters(statement, search: str, only_active: bool):
    if search:
        statement = statement.where(Product.name.ilike(f"%{search.strip()}%"))
    if only_active:
        statement = statement.where(Product.is_active.is_(True))
    return statement


def list_products(
    search: str = "",
    only_active: bool = False,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Product], int]:
    with session_scope() as session:
        total = session.scalar(
            _apply_filters(select(func.count()).select_from(Product), search, only_active)
        )
        rows = session.scalars(
            _apply_filters(select(Product), search, only_active)
            .order_by(Product.name)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), int(total or 0)


def sellable_products(search: str = "", limit: int = 50) -> list[Product]:
    """Productos que se pueden agregar al carrito ahora mismo.

    Se excluyen los inactivos y los agotados para que el mostrador no ofrezca
    algo que no puede entregar.
    """
    with session_scope() as session:
        statement = select(Product).where(Product.is_active.is_(True))
        if search:
            statement = statement.where(Product.name.ilike(f"%{search.strip()}%"))
        statement = (
            statement.where(or_(Product.stock.is_(None), Product.stock > 0))
            .order_by(Product.name)
            .limit(limit)
        )
        return list(session.scalars(statement).all())


def get_product(product_id: int) -> Product:
    with session_scope() as session:
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("El producto ya no existe.")
        return product


def low_stock(threshold: int = 5) -> list[Product]:
    with session_scope() as session:
        return list(
            session.scalars(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.stock.is_not(None),
                    Product.stock <= threshold,
                )
                .order_by(Product.stock)
            ).all()
        )
