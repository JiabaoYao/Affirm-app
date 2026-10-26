from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today() -> date:
    return utcnow().date()


def as_utc(value: datetime) -> datetime:
    """SQLite (tests) drops the timezone on read; Postgres keeps it. Treat naive values as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _enum(enum_cls: type[enum.Enum]) -> Enum:
    # Stored as VARCHAR + CHECK instead of a native Postgres ENUM, so adding a value needs no migration.
    return Enum(enum_cls, native_enum=False, length=20, validate_strings=True)


Money = Numeric(12, 2)
Rate = Numeric(5, 4)


class UserRole(str, enum.Enum):
    consumer = "consumer"
    merchant = "merchant"
    admin = "admin"


class MerchantStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"


class TierDecision(str, enum.Enum):
    approve = "approve"
    review = "review"
    decline = "decline"


class TransactionStatus(str, enum.Enum):
    in_review = "in_review"      # flagged by the risk rules, waiting for an admin
    approved = "approved"        # offers available, consumer hasn't picked one yet
    declined = "declined"
    cancelled = "cancelled"      # consumer walked away before picking a plan
    authorized = "authorized"    # plan accepted, waiting for the merchant to capture (ship)
    captured = "captured"        # merchant shipped; the loan is live
    voided = "voided"            # merchant cancelled the order before capture


class PlanStatus(str, enum.Enum):
    pending_capture = "pending_capture"
    active = "active"
    paid_off = "paid_off"
    voided = "voided"


class InstallmentStatus(str, enum.Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"


class PaymentMethodKind(str, enum.Enum):
    bank = "bank"
    card = "card"


class PaymentSource(str, enum.Enum):
    manual = "manual"
    autopay = "autopay"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant_profile: Mapped[MerchantProfile | None] = relationship(back_populates="user", lazy="joined")

    @property
    def merchant_status(self) -> MerchantStatus | None:
        return self.merchant_profile.status if self.merchant_profile else None

    @property
    def business_name(self) -> str | None:
        return self.merchant_profile.business_name if self.merchant_profile else None


class MerchantProfile(Base):
    """A merchant's business account. Keyed by the owner's user id, so merchant_id == users.id everywhere."""

    __tablename__ = "merchant_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[MerchantStatus] = mapped_column(_enum(MerchantStatus), default=MerchantStatus.pending)
    # What the merchant pays Affirm per captured order, plus an extra rate when it funds a 0% APR promo.
    fee_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0.0300"))
    promo_fee_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("0.0300"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="merchant_profile", lazy="joined")
    programs: Mapped[list[MerchantProgram]] = relationship(
        back_populates="merchant", order_by="MerchantProgram.term_months", lazy="selectin"
    )

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def full_name(self) -> str:
        return self.user.full_name


class MerchantProgram(Base):
    """One financing term a merchant offers at checkout. Replaces the old global plan_offers table."""

    __tablename__ = "merchant_programs"
    __table_args__ = (UniqueConstraint("merchant_id", "term_months"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant_profiles.user_id"), index=True)
    term_months: Mapped[int]
    # Merchant-funded 0% APR: the consumer pays no interest, the merchant pays promo_fee_rate on top.
    zero_apr_promo: Mapped[bool] = mapped_column(default=False)
    min_amount: Mapped[Decimal] = mapped_column(Money)
    max_amount: Mapped[Decimal] = mapped_column(Money)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant: Mapped[MerchantProfile] = relationship(back_populates="programs")


class RiskTier(Base):
    """Underwriting rule for a credit score band: approve / review / decline, and the APR, limit and max term."""

    __tablename__ = "risk_tiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    min_score: Mapped[int]
    max_score: Mapped[int]
    decision: Mapped[TierDecision] = mapped_column(_enum(TierDecision))
    apr: Mapped[Decimal] = mapped_column(Rate)
    max_amount: Mapped[Decimal] = mapped_column(Money)
    max_term_months: Mapped[int]


class CreditCheck(Base):
    """A (mock) soft credit check: never affects the score, so the consumer can run it any time."""

    __tablename__ = "credit_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[int]
    risk_tier_id: Mapped[int] = mapped_column(ForeignKey("risk_tiers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tier: Mapped[RiskTier] = relationship(lazy="joined")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant_profiles.user_id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Money)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant: Mapped[MerchantProfile] = relationship(lazy="joined")

    @property
    def merchant_name(self) -> str:
        return self.merchant.business_name


class Transaction(Base):
    """A financed checkout: application, decision, then the order the merchant captures or voids."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    consumer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant_profiles.user_id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[TransactionStatus] = mapped_column(_enum(TransactionStatus))
    credit_check_id: Mapped[int | None] = mapped_column(ForeignKey("credit_checks.id"), nullable=True)
    # Adverse-action text for a decline, or why it was sent to review. Shown to the consumer, not the merchant.
    decision_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_fee: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped[Product] = relationship(lazy="joined")
    merchant: Mapped[MerchantProfile] = relationship(lazy="joined")
    consumer: Mapped[User] = relationship(lazy="joined")
    credit_check: Mapped[CreditCheck | None] = relationship(lazy="joined")
    plan: Mapped[Plan | None] = relationship(back_populates="transaction", uselist=False)

    @property
    def product_name(self) -> str:
        return self.product.name

    @property
    def merchant_name(self) -> str:
        return self.merchant.business_name

    @property
    def customer_email(self) -> str:
        return self.consumer.email

    @property
    def customer_name(self) -> str:
        return self.consumer.full_name

    @property
    def credit_score(self) -> int | None:
        return self.credit_check.score if self.credit_check else None

    @property
    def risk_tier(self) -> str | None:
        return self.credit_check.tier.name if self.credit_check else None

    @property
    def plan_id(self) -> int | None:
        return self.plan.id if self.plan else None


class PaymentMethod(Base):
    """A mock bank account or debit card. Only the last 4 digits are stored."""

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[PaymentMethodKind] = mapped_column(_enum(PaymentMethodKind))
    label: Mapped[str] = mapped_column(String(60))
    last4: Mapped[str] = mapped_column(String(4))
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Soft delete: past payments keep pointing at it.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Unique: one plan per purchase. Also turns a double-submitted "select plan" into an IntegrityError.
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), unique=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("merchant_programs.id"))
    # Copied from the program and risk tier so later rule changes never rewrite an existing loan.
    term_months: Mapped[int]
    apr: Mapped[Decimal] = mapped_column(Rate)
    principal: Mapped[Decimal] = mapped_column(Money)
    monthly_payment: Mapped[Decimal] = mapped_column(Money)
    total_interest: Mapped[Decimal] = mapped_column(Money)
    amount_paid: Mapped[Decimal] = mapped_column(Money)
    autopay_day: Mapped[int]
    autopay_enabled: Mapped[bool] = mapped_column(default=False)
    payment_method_id: Mapped[int | None] = mapped_column(ForeignKey("payment_methods.id"), nullable=True)
    status: Mapped[PlanStatus] = mapped_column(_enum(PlanStatus))
    agreement_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction: Mapped[Transaction] = relationship(back_populates="plan", lazy="joined")
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

    @property
    def days_past_due(self) -> int:
        if self.status != PlanStatus.active:
            return 0
        return max((i.days_past_due for i in self.installments), default=0)

    @property
    def overdue_amount(self) -> Decimal:
        return sum((i.amount_remaining for i in self.installments if i.days_past_due > 0), Decimal("0.00"))

    @property
    def product_name(self) -> str:
        return self.transaction.product_name

    @property
    def merchant_name(self) -> str:
        return self.transaction.merchant_name

    @property
    def zero_apr_promo(self) -> bool:
        return self.apr == 0


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

    @property
    def days_past_due(self) -> int:
        if self.status == InstallmentStatus.paid:
            return 0
        return max((today() - self.due_date).days, 0)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    payment_method_id: Mapped[int | None] = mapped_column(ForeignKey("payment_methods.id"), nullable=True)
    source: Mapped[PaymentSource] = mapped_column(_enum(PaymentSource), default=PaymentSource.manual)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    plan: Mapped[Plan] = relationship(back_populates="payments")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500))
    # Frontend route to open, e.g. "/app/loans/3".
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Lets the daily job send each reminder once, e.g. "overdue:42".
    dedupe_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Who changed what and when, for admin and merchant state changes."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int]
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actor: Mapped[User] = relationship(lazy="joined")

    @property
    def actor_email(self) -> str:
        return self.actor.email


class RevokedToken(Base):
    """JWT denylist: a token whose jti is here is rejected even before it expires (logout)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
