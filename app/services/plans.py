from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Installment,
    InstallmentStatus,
    MerchantProgram,
    PaymentMethod,
    Plan,
    PlanStatus,
    RiskTier,
    Transaction,
    TransactionStatus,
    utcnow,
)
from app.services.amortization import add_months, build_schedule, monthly_payment, to_cents

# Platform-wide limits a merchant program must stay within.
MIN_FINANCED_AMOUNT = Decimal("50.00")
MAX_FINANCED_AMOUNT = Decimal("30000.00")
ALLOWED_TERMS = (3, 6, 12, 24)


@dataclass(frozen=True)
class Offer:
    """A merchant program priced for one consumer's risk tier."""

    program: MerchantProgram
    apr: Decimal

    @property
    def term_months(self) -> int:
        return self.program.term_months

    @property
    def zero_apr_promo(self) -> bool:
        return self.program.zero_apr_promo


def offers_for(programs: list[MerchantProgram], tier: RiskTier, amount: Decimal) -> list[Offer]:
    """Programs that fit the amount and the tier's max term. Promo programs are 0% APR, the rest use the tier APR."""
    return [
        Offer(program=p, apr=Decimal("0.0000") if p.zero_apr_promo else tier.apr)
        for p in sorted(programs, key=lambda p: p.term_months)
        if p.active and p.min_amount <= amount <= p.max_amount and p.term_months <= tier.max_term_months
    ]


def as_low_as(programs: list[MerchantProgram], best_apr: Decimal, amount: Decimal) -> tuple[Decimal, int] | None:
    """Lowest monthly payment for promo messaging ("as low as $X/mo"), assuming the best risk tier."""
    quotes = [
        (monthly_payment(amount, Decimal(0) if p.zero_apr_promo else best_apr, p.term_months), p.term_months)
        for p in programs
        if p.active and p.min_amount <= amount <= p.max_amount
    ]
    return min(quotes, default=None)


def default_autopay_day(today: date) -> int:
    return min(today.day, 28)


@dataclass(frozen=True)
class PlanQuote:
    term_months: int
    apr: Decimal
    zero_apr_promo: bool
    monthly_payment: Decimal
    total_interest: Decimal
    total_cost: Decimal


def quote(amount: Decimal, offer: Offer, today: date) -> PlanQuote:
    schedule = build_schedule(amount, offer.apr, offer.term_months, today, default_autopay_day(today))
    return PlanQuote(
        term_months=offer.term_months,
        apr=offer.apr,
        zero_apr_promo=offer.zero_apr_promo,
        monthly_payment=schedule.monthly_payment,
        total_interest=schedule.total_interest,
        total_cost=schedule.total_cost,
    )


def build_plan(*, user_id: int, transaction_id: int, program_id: int, term_months: int, apr: Decimal,
               principal: Decimal, autopay_day: int, now: datetime, autopay_enabled: bool = False,
               payment_method_id: int | None = None, status: PlanStatus = PlanStatus.active) -> Plan:
    """Create an (unsaved) Plan with its full installment schedule."""
    schedule = build_schedule(principal, apr, term_months, now.date(), autopay_day)
    return Plan(
        user_id=user_id,
        transaction_id=transaction_id,
        program_id=program_id,
        term_months=term_months,
        apr=apr,
        principal=principal,
        monthly_payment=schedule.monthly_payment,
        total_interest=schedule.total_interest,
        amount_paid=Decimal("0.00"),
        autopay_day=autopay_day,
        autopay_enabled=autopay_enabled,
        payment_method_id=payment_method_id,
        status=status,
        agreement_accepted_at=now,
        created_at=now,
        activated_at=now if status == PlanStatus.active else None,
        installments=[
            Installment(
                seq=row.seq,
                due_date=row.due_date,
                amount_due=row.amount_due,
                principal=row.principal,
                interest=row.interest,
                amount_paid=Decimal("0.00"),
                status=InstallmentStatus.pending,
            )
            for row in schedule.rows
        ],
        payments=[],
    )


def _already_selected() -> AppError:
    return AppError(409, "PLAN_ALREADY_SELECTED", "A plan has already been selected for this purchase.")


def tx_offers(tx: Transaction) -> list[Offer]:
    if tx.credit_check is None:
        return []
    return offers_for(tx.merchant.programs, tx.credit_check.tier, tx.amount)


def select_plan(db: Session, transaction: Transaction, term_months: int, *, agree: bool,
                autopay_day: int | None = None, autopay_enabled: bool = False,
                payment_method: PaymentMethod | None = None, now: datetime | None = None) -> Plan:
    """Accept the loan agreement for one offer: creates the plan (pending capture) and authorizes the order.
    Flushes but doesn't commit."""
    if transaction.status in (TransactionStatus.authorized, TransactionStatus.captured):
        raise _already_selected()
    if transaction.status != TransactionStatus.approved:
        raise AppError(409, "NOT_APPROVED", f"This purchase is {transaction.status.value.replace('_', ' ')}, "
                                            f"so a plan can't be selected.")
    if not agree:
        raise AppError(422, "AGREEMENT_REQUIRED", "You must accept the loan agreement to continue.")
    if autopay_enabled and payment_method is None:
        raise AppError(422, "PAYMENT_METHOD_REQUIRED", "Add a payment method to turn on autopay.")

    offers = {offer.term_months: offer for offer in tx_offers(transaction)}
    offer = offers.get(term_months)
    if offer is None:
        terms = ", ".join(str(term) for term in sorted(offers))
        raise AppError(422, "INVALID_TERM", f"{term_months}-month plan isn't available for this purchase. "
                                             f"Available terms: {terms}.")

    now = now or utcnow()
    plan = build_plan(
        user_id=transaction.consumer_id,
        transaction_id=transaction.id,
        program_id=offer.program.id,
        term_months=offer.term_months,
        apr=offer.apr,
        principal=transaction.amount,
        autopay_day=autopay_day or default_autopay_day(now.date()),
        autopay_enabled=autopay_enabled,
        payment_method_id=payment_method.id if payment_method else None,
        status=PlanStatus.pending_capture,
        now=now,
    )
    db.add(plan)
    merchant = transaction.merchant
    fee_rate = merchant.fee_rate + (merchant.promo_fee_rate if offer.zero_apr_promo else 0)
    transaction.status = TransactionStatus.authorized
    transaction.merchant_fee = to_cents(transaction.amount * fee_rate)
    try:
        db.flush()
    except IntegrityError:
        # Another request created a plan for this transaction first (unique plans.transaction_id).
        db.rollback()
        raise _already_selected()
    return plan


def _ensure_open(plan: Plan) -> None:
    if plan.status == PlanStatus.paid_off:
        raise AppError(409, "PLAN_PAID_OFF", "This plan is already paid off.")
    if plan.status == PlanStatus.voided:
        raise AppError(409, "PLAN_VOIDED", "This plan was cancelled by the merchant.")


def change_autopay_day(plan: Plan, autopay_day: int) -> None:
    """Move the due date of every installment that isn't fully paid to the new day of the month."""
    _ensure_open(plan)
    plan.autopay_day = autopay_day
    start = plan.created_at.date()
    for installment in plan.installments:
        if installment.status != InstallmentStatus.paid:
            installment.due_date = add_months(start, installment.seq, autopay_day)


def set_autopay(plan: Plan, enabled: bool, payment_method: PaymentMethod | None) -> None:
    _ensure_open(plan)
    if enabled and payment_method is None:
        raise AppError(422, "PAYMENT_METHOD_REQUIRED", "Add a payment method to turn on autopay.")
    plan.autopay_enabled = enabled
    if payment_method is not None:
        plan.payment_method_id = payment_method.id
