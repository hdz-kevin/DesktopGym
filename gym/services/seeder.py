"""Datos de prueba para desarrollar contra una base real.

No es un modulo de la aplicacion de recepcion: se invoca a mano con
`python -m gym.seed`. `seed` vacia primero y luego carga socios, visitas,
productos y ventas lo bastante variados como para recorrer todas las pantallas.
`reset` deja solo el catalogo inicial de precios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete

from gym.config import photos_dir
from gym.data.database import session_scope
from gym.data.models import (
    Member,
    Membership,
    Payment,
    Plan,
    PlanCategory,
    Product,
    ProductSale,
    Sale,
    Visit,
)
from gym.data.schema import populate_seed_catalog
from gym.domain.dates import add_months, start_of_day
from gym.domain.enums import MemberGender
from gym.services import members as members_service
from gym.services import memberships as memberships_service
from gym.services import products as products_service
from gym.services import sales as sales_service
from gym.services import visits as visits_service
from gym.services.sales import Cart

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedSummary:
    members: int
    memberships: int
    visits: int
    products: int
    sales: int


_MEMBERS: list[tuple[str, MemberGender, date | None]] = [
    ("Ana Lucia Ramirez", MemberGender.FEMALE, date(1995, 3, 14)),
    ("Carlos Mendoza", MemberGender.MALE, date(1988, 11, 2)),
    ("Sofia Herrera", MemberGender.FEMALE, date(2001, 7, 22)),
    ("Diego Navarro", MemberGender.MALE, date(2004, 1, 9)),
    ("Valeria Cruz", MemberGender.FEMALE, date(2003, 5, 30)),
    ("Luis Ortega", MemberGender.MALE, date(1979, 9, 18)),
    ("Mariana Soto", MemberGender.FEMALE, date(1992, 12, 5)),
    ("Jorge Pena", MemberGender.MALE, date(1985, 4, 27)),
    ("Roberto Diaz", MemberGender.MALE, date(1972, 8, 11)),
    ("Patricia Vega", MemberGender.FEMALE, date(1990, 2, 16)),
    ("Andres Molina", MemberGender.MALE, date(1998, 6, 3)),
    ("Elena Rios", MemberGender.FEMALE, date(1983, 10, 21)),
    ("Pablo Jimenez", MemberGender.MALE, date(1996, 1, 28)),
    ("Lucia Fernandez", MemberGender.FEMALE, date(1999, 4, 8)),
    ("Hector Salazar", MemberGender.MALE, None),
    ("Carmen Nunez", MemberGender.FEMALE, date(1976, 7, 19)),
    ("Fernanda Gil", MemberGender.FEMALE, date(1994, 9, 1)),
    ("Miguel Angel Torres", MemberGender.MALE, date(2002, 11, 13)),
    ("Daniela Pacheco", MemberGender.FEMALE, date(1997, 3, 25)),
    ("Ricardo Avila", MemberGender.MALE, date(1981, 5, 7)),
    ("Isabel Leon", MemberGender.FEMALE, date(1993, 8, 29)),
    ("Tomas Ibarra", MemberGender.MALE, date(2000, 12, 12)),
    ("Gabriela Ramos", MemberGender.FEMALE, date(1987, 2, 4)),
    ("Oscar Beltran", MemberGender.MALE, None),
    ("Monica Fuentes", MemberGender.FEMALE, date(1991, 6, 17)),
    ("Raul Espinoza", MemberGender.MALE, date(1968, 10, 6)),
    ("Alejandra Campos", MemberGender.FEMALE, date(2005, 1, 23)),
    ("Francisco Reyes", MemberGender.MALE, date(1984, 7, 14)),
    ("Natalia Vargas", MemberGender.FEMALE, date(1996, 9, 9)),
    ("Eduardo Castillo", MemberGender.MALE, date(1975, 3, 31)),
    ("Paola Miranda", MemberGender.FEMALE, None),
    ("Ivan Guerrero", MemberGender.MALE, date(2003, 11, 20)),
]

_PRODUCTS: list[tuple[str, int, int]] = [
    ("Agua 1L", 1800, 72),
    ("Agua 1.5L", 2200, 38),
    ("Barra Proteica Met-Rx 30g", 4200, 9),
    ("Electrolit", 3000, 32),
    ("Monster 500 ml", 3800, 20),
    ("Scoop Proteina", 4800, 5),
    ("Scoop Creatina", 2800, 14),
    ("Proteina Naked Vainilla 600g", 54900, 7),
    ("Creatina Bird Man 500g", 42900, 2),
    ("Proteina Gold Standar 2kg", 134900, 5),
    ("Preentreno Psychotic 200g", 38900, 6),
]


def reset_to_catalog() -> None:
    """Borra el movimiento del gimnasio y deja el catalogo inicial de precios.

    Socios, visitas, productos y ventas desaparecen. Las categorias General y
    Estudiante vuelven a los precios de fabrica, aunque se hayan editado.
    Fotos sueltas se eliminan; respaldos y ajustes no se tocan.
    """
    with session_scope() as session:
        session.execute(delete(ProductSale))
        session.execute(delete(Sale))
        session.execute(delete(Visit))
        session.execute(delete(Payment))
        session.execute(delete(Membership))
        session.execute(delete(Member))
        session.execute(delete(Product))
        session.execute(delete(Plan))
        session.execute(delete(PlanCategory))
        populate_seed_catalog(session)
    _clear_photos()
    logger.info("Base restablecida al catalogo inicial")


def seed() -> SeedSummary:
    """Vacia la base, restaura el catalogo y carga datos de prueba."""
    reset_to_catalog()
    catalog = _plan_ids()
    ids = _seed_members()
    memberships = _seed_memberships(ids, catalog)
    visits = _seed_visits()
    products = _seed_products()
    sales = _seed_sales(products)
    summary = SeedSummary(
        members=len(ids),
        memberships=memberships,
        visits=visits,
        products=len(products),
        sales=sales,
    )
    logger.info(
        "Datos de prueba cargados: %s socios, %s membresias, %s visitas, %s productos, %s ventas",
        summary.members,
        summary.memberships,
        summary.visits,
        summary.products,
        summary.sales,
    )
    return summary


def _clear_photos() -> None:
    folder = photos_dir()
    for path in folder.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)


def _plan_ids() -> dict[str, int]:
    ids: dict[str, int] = {}
    for plan in memberships_service.list_plans():
        ids[f"{plan.plan_category.name}:{plan.name}"] = plan.id
    return ids


def _seed_members() -> dict[str, int]:
    ids: dict[str, int] = {}
    for name, gender, birth_date in _MEMBERS:
        ids[name] = members_service.create_member(
            members_service.MemberForm(name=name, gender=gender, birth_date=birth_date)
        )
    return ids


def _seed_memberships(ids: dict[str, int], catalog: dict[str, int]) -> int:
    today = date.today()
    general_month = catalog["General:Mensual"]
    general_weeks = catalog["General:2 Semanas"]
    student_month = catalog["Estudiante:Mensual"]
    student_weeks = catalog["Estudiante:2 Semanas"]

    def give(name: str, plan_id: int, start: date, *, renew: bool = False) -> int:
        membership_id = memberships_service.create_membership(ids[name], plan_id, start=start)
        if renew:
            memberships_service.renew_membership(membership_id, plan_id)
        return membership_id

    # Activos con distintos planes y antiguedades.
    give("Ana Lucia Ramirez", general_month, today - timedelta(days=12))
    give("Carlos Mendoza", general_month, today - timedelta(days=5))
    give("Sofia Herrera", general_weeks, today - timedelta(days=3))
    give("Diego Navarro", student_month, today - timedelta(days=20))
    give("Valeria Cruz", student_weeks, today - timedelta(days=6))
    give("Fernanda Gil", general_month, today - timedelta(days=18))
    give("Miguel Angel Torres", student_month, today - timedelta(days=9))
    give("Daniela Pacheco", general_weeks, today - timedelta(days=1))
    give("Ricardo Avila", general_month, today)
    give("Tomas Ibarra", general_month, today - timedelta(days=22))
    give("Gabriela Ramos", student_month, today - timedelta(days=4))
    give("Alejandra Campos", student_weeks, today - timedelta(days=8))
    give("Natalia Vargas", general_month, today - timedelta(days=15))
    give("Ivan Guerrero", student_month, today - timedelta(days=2))

    # Vence hoy al final del dia: el socio todavia puede pasar.
    give("Isabel Leon", general_month, add_months(start_of_day(today), -1).date())

    # Por vencer en pocos dias.
    give(
        "Luis Ortega",
        general_month,
        add_months(start_of_day(today + timedelta(days=4)), -1).date(),
    )

    # Vigente y ya pago el siguiente periodo.
    give("Mariana Soto", general_month, today - timedelta(days=10), renew=True)

    # Vencio hace meses y se reactivo hoy.
    give("Jorge Pena", general_month, today - timedelta(days=80), renew=True)

    # Dos planes distintos en el historial, incluyendo un cambio de categoria.
    mixed = give("Monica Fuentes", student_weeks, today - timedelta(days=40))
    memberships_service.renew_membership(mixed, general_month, start=today - timedelta(days=20))

    # Vencidos sin renovar.
    give("Roberto Diaz", general_month, today - timedelta(days=100))
    give("Patricia Vega", student_month, today - timedelta(days=70))
    give("Andres Molina", general_weeks, today - timedelta(days=21))
    give("Elena Rios", general_month, today - timedelta(days=50))
    give("Raul Espinoza", general_month, today - timedelta(days=200))
    give("Francisco Reyes", student_weeks, today - timedelta(days=18))
    give("Eduardo Castillo", general_month, today - timedelta(days=45))

    # Sin membresia: Pablo, Lucia, Hector, Carmen, Oscar, Paola.

    return memberships_service.membership_stats().total


def _seed_visits() -> int:
    count = 0
    today_hours = (7, 8, 10, 12, 17)
    for hour in today_hours:
        visits_service.create_visit(4000, _at(0, hour))
        count += 1
    visits_service.create_visit(5000, _at(0, 19))
    count += 1

    for days in range(1, 8):
        visits_service.create_visit(4000, _at(days, 8 + days % 6))
        count += 1
        if days % 2 == 0:
            visits_service.create_visit(3500, _at(days, 18))
            count += 1

    for days in (10, 12, 15, 18, 21, 24, 27):
        visits_service.create_visit(4000, _at(days, 9))
        count += 1

    for days in (35, 40, 48, 55, 62):
        visits_service.create_visit(4000, _at(days, 11))
        count += 1
    return count


def _seed_products() -> dict[str, Product]:
    created: dict[str, Product] = {}
    for name, price_cents, stock in _PRODUCTS:
        product_id = products_service.create_product(
            products_service.ProductForm(name=name, price_cents=price_cents, stock=stock)
        )
        created[name] = products_service.get_product(product_id)
    psychotic = created["Preentreno Psychotic 200g"]
    products_service.set_active(psychotic.id, False)
    created["Preentreno Psychotic 200g"] = products_service.get_product(psychotic.id)
    return created


def _seed_sales(products: dict[str, Product]) -> int:
    tickets: list[tuple[int, list[tuple[str, int]]]] = [
        (0, [("Agua 1L", 2), ("Electrolit", 1)]),
        (0, [("Monster 500 ml", 1), ("Barra Proteica Met-Rx 30g", 1)]),
        (0, [("Scoop Proteina", 1)]),
        (0, [("Agua 1.5L", 1), ("Scoop Creatina", 1)]),
        (1, [("Agua 1L", 3)]),
        (2, [("Electrolit", 2), ("Monster 500 ml", 1)]),
        (3, [("Barra Proteica Met-Rx 30g", 2)]),
        (5, [("Scoop Creatina", 1), ("Agua 1L", 1)]),
        (6, [("Agua 1.5L", 2), ("Electrolit", 1)]),
        (8, [("Proteina Naked Vainilla 600g", 1)]),
        (12, [("Monster 500 ml", 1), ("Barra Proteica Met-Rx 30g", 1)]),
        (15, [("Agua 1L", 2), ("Scoop Proteina", 1)]),
        (20, [("Creatina Bird Man 500g", 1)]),
        (22, [("Scoop Creatina", 1), ("Preentreno Psychotic 200g", 1)]),
        (28, [("Agua 1L", 4), ("Monster 500 ml", 1)]),
        (35, [("Proteina Gold Standar 2kg", 1)]),
        (40, [("Electrolit", 1), ("Barra Proteica Met-Rx 30g", 1)]),
        (50, [("Creatina Bird Man 500g", 1), ("Agua 1L", 1)]),
    ]
    for days_ago, lines in tickets:
        cart = Cart()
        for name, quantity in lines:
            cart.add(products[name], quantity)
        sales_service.checkout(cart, sold_at=_at(days_ago, 11 + days_ago % 7, 15))
        for name, quantity in lines:
            products[name].stock -= quantity
    return len(tickets)


def _at(days_ago: int, hour: int, minute: int = 0) -> datetime:
    now = datetime.now()
    moment = now - timedelta(days=days_ago)
    if days_ago == 0:
        hour = min(hour, max(0, now.hour))
    return moment.replace(hour=hour, minute=minute, second=0, microsecond=0)
