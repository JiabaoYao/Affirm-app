from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_cls: type[enum.Enum]) -> Enum:
    # Stored as VARCHAR + CHECK instead of a native Postgres ENUM, so adding a value needs no migration.
    return Enum(enum_cls, native_enum=False, length=20, validate_strings=True)


Money = Numeric(12, 2)
Rate = Numeric(5, 4)


class UserRole(str, enum.Enum):
    consumer = "consumer"
    merchant = "merchant"


class TransactionStatus(str, enum.Enum):
    pending_plan = "pending_plan"
    financed = "financed"


class PlanStatus(str, enum.Enum):
    active = "active"
    paid_off = "paid_off"


class InstallmentStatus(str, enum.Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Money)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    consumer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[TransactionStatus] = mapped_column(_enum(TransactionStatus), default=TransactionStatus.pending_plan)
    service_fee: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(lazy="joined")
    plan: Mapped[Plan | None] = relationship(back_populates="transaction", uselist=False)

    @property
    def product_name(self) -> str:
        return self.product.name


class PlanOffer(Base):
    __tablename__ = "plan_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    term_months: Mapped[int] = mapped_column(unique=True)
    apr: Mapped[Decimal] = mapped_column(Rate)
    min_amount: Mapped[Decimal] = mapped_column(Money)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Unique: one plan per purchase. Also turns a double-submitted "select plan" into an IntegrityError.
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), unique=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("plan_offers.id"))
    # Copied from the offer so later offer changes never rewrite an existing loan.
    term_months: Mapped[int]
    apr: Mapped[Decimal] = mapped_column(Rate)
    principal: Mapped[Decimal] = mapped_column(Money)
    monthly_payment: Mapped[Decimal] = mapped_column(Money)
    total_interest: Mapped[Decimal] = mapped_column(Money)
    amount_paid: Mapped[Decimal] = mapped_column(Money)
    autopay_day: Mapped[int]
    status: Mapped[PlanStatus] = mapped_column(_enum(PlanStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    transaction: Mapped[Transaction] = relationship(back_populates="plan")
    installments: Mapped[list[Installment]] = relationship(
        back_populates="plan", order_by="Installment.seq", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="plan", order_by="Payment.paid_at", cascade="all, delete-orphan"
    )

    @property
    def remaining_balance(self) -> Decimal:
        return self.principal + self.total_interest - self.amount_paid

    @property
    def next_due_date(self) -> date | None:
        return next((i.due_date for i in self.installments if i.status != InstallmentStatus.paid), None)


class Installment(Base):
    __tablename__ = "installments"
    __table_args__ = (UniqueConstraint("plan_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    seq: Mapped[int]
    due_date: Mapped[date] = mapped_column(Date)
    amount_due: Mapped[Decimal] = mapped_column(Money)
    principal: Mapped[Decimal] = mapped_column(Money)
    interest: Mapped[Decimal] = mapped_column(Money)
    amount_paid: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[InstallmentStatus] = mapped_column(_enum(InstallmentStatus))

    plan: Mapped[Plan] = relationship(back_populates="installments")

    @property
    def amount_remaining(self) -> Decimal:
        return self.amount_due - self.amount_paid


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    plan: Mapped[Plan] = relationship(back_populates="payments")


class RevokedToken(Base):
    """JWT denylist: a token whose jti is here is rejected even before it expires (logout)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
