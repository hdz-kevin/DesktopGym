"""Modelos SQLAlchemy del dominio del gimnasio.

Los estados de socio y membresia no son columnas: se derivan de las fechas.
Se exponen como `hybrid_property` para que la misma regla sirva en Python y
dentro de un WHERE de SQL, evitando cargar tablas enteras en memoria solo
para filtrar por "activo" o "vencido".
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    case,
    exists,
    func,
    select,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from gym.data.types import EnumValue
from gym.domain.dates import age_from
from gym.domain.enums import (
    DurationUnit,
    MemberGender,
    MembershipStatus,
    MemberStatus,
)
from gym.domain.rules import initials


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class Member(Base, TimestampMixin):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    gender: Mapped[MemberGender] = mapped_column(EnumValue(MemberGender, 10), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    photo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        order_by="desc(Membership.updated_at)",
    )

    __table_args__ = (Index("ix_members_name", "name"),)

    @hybrid_property
    def status(self) -> MemberStatus:
        if not self.memberships:
            return MemberStatus.NO_MEMBERSHIP
        if any(m.status is MembershipStatus.ACTIVE for m in self.memberships):
            return MemberStatus.ACTIVE
        return MemberStatus.EXPIRED

    @status.expression
    @classmethod
    def status(cls):
        has_membership = exists(select(Membership.id).where(Membership.member_id == cls.id))
        has_active_payment = exists(
            select(Payment.id)
            .join(Membership, Payment.membership_id == Membership.id)
            .where(
                Membership.member_id == cls.id,
                Payment.end_date >= func.datetime("now", "localtime"),
            )
        )
        return case(
            (~has_membership, MemberStatus.NO_MEMBERSHIP.value),
            (has_active_payment, MemberStatus.ACTIVE.value),
            else_=MemberStatus.EXPIRED.value,
        )

    @property
    def age(self) -> int | None:
        return age_from(self.birth_date)

    @property
    def initials(self) -> str:
        return initials(self.name)

    def active_membership(self) -> Membership | None:
        return next((m for m in self.memberships if m.status is MembershipStatus.ACTIVE), None)

    def latest_membership(self) -> Membership | None:
        if not self.memberships:
            return None
        # SQLite suele guardar datetime al segundo: dos altas seguidas empatan
        # en updated_at y max() se quedaria con la primera (la mas vieja).
        return max(self.memberships, key=lambda m: (m.updated_at, m.id))


class PlanCategory(Base, TimestampMixin):
    __tablename__ = "plan_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    plans: Mapped[list[Plan]] = relationship(back_populates="plan_category", order_by="Plan.id")
    memberships: Mapped[list[Membership]] = relationship(back_populates="plan_category")


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_category_id: Mapped[int] = mapped_column(
        ForeignKey("plan_categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[DurationUnit] = mapped_column(EnumValue(DurationUnit, 10), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    plan_category: Mapped[PlanCategory] = relationship(back_populates="plans")
    payments: Mapped[list[Payment]] = relationship(back_populates="plan")

    @property
    def label(self) -> str:
        return f"{self.plan_category.name} · {self.name}"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_plans_amount_positive"),
        CheckConstraint("price_cents >= 0", name="ck_plans_price_non_negative"),
    )


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    plan_category_id: Mapped[int] = mapped_column(
        ForeignKey("plan_categories.id", ondelete="RESTRICT"), nullable=False
    )

    member: Mapped[Member] = relationship(back_populates="memberships")
    plan_category: Mapped[PlanCategory] = relationship(back_populates="memberships")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="membership",
        cascade="all, delete-orphan",
        order_by="desc(Payment.id)",
    )

    @hybrid_property
    def status(self) -> MembershipStatus:
        if any(p.end_date >= datetime.now() for p in self.payments):
            return MembershipStatus.ACTIVE
        return MembershipStatus.EXPIRED

    @status.expression
    @classmethod
    def status(cls):
        active = exists(
            select(Payment.id).where(
                Payment.membership_id == cls.id,
                Payment.end_date >= func.datetime("now", "localtime"),
            )
        )
        return case((active, MembershipStatus.ACTIVE.value), else_=MembershipStatus.EXPIRED.value)

    @property
    def recent_payment(self) -> Payment | None:
        return self.payments[0] if self.payments else None

    @property
    def current_plan(self) -> Plan | None:
        payment = self.recent_payment
        return payment.plan if payment else None

    @property
    def current_plan_label(self) -> str:
        plan = self.current_plan
        return plan.label if plan else "—"

    @property
    def total_paid_cents(self) -> int:
        return sum(p.price_paid_cents for p in self.payments)


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    membership: Mapped[Membership] = relationship(back_populates="payments")
    plan: Mapped[Plan] = relationship(back_populates="payments")

    __table_args__ = (
        Index("ix_payments_membership_end", "membership_id", "end_date"),
        Index("ix_payments_start_date", "start_date"),
        CheckConstraint("end_date >= start_date", name="ck_payments_dates_ordered"),
    )

    @property
    def is_current(self) -> bool:
        now = datetime.now()
        return self.start_date <= now <= self.end_date


class Visit(Base, TimestampMixin):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_visits_visit_at", "visit_at"),
        CheckConstraint("price_cents >= 0", name="ck_visits_price_non_negative"),
    )


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    lines: Mapped[list[ProductSale]] = relationship(back_populates="product")

    __table_args__ = (
        Index("ix_products_name", "name"),
        CheckConstraint("price_cents >= 0", name="ck_products_price_non_negative"),
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )


class Sale(Base, TimestampMixin):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    # Evento, no estado: el ticket se conserva y el corte ignora las anuladas.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lines: Mapped[list[ProductSale]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_sales_sold_at", "sold_at"),)

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)


class ProductSale(Base, TimestampMixin):
    """Linea de venta con copia del nombre y precio al momento de vender.

    El precio se congela aqui para que cambiar el precio de un producto no
    altere el historial de ventas ni los cortes de caja ya emitidos.
    """

    __tablename__ = "product_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    sale: Mapped[Sale] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship(back_populates="lines")

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_product_sales_quantity_positive"),)
