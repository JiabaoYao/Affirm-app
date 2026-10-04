from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Installment,
    InstallmentStatus,
    Plan,
    PlanOffer,
    PlanStatus,
    Transaction,
    TransactionStatus,
    utcnow,
)
from app.services.amortization import add_months, build_schedule, to_cents

MIN_FINANCED_AMOUNT = Decimal("50.00")
MAX_FINANCED_AMOUNT = Decimal("30000.00")
SERVICE_FEE_RATE = Decimal("0.03")

# (term_months, apr, min_amount)
DEFAULT_OFFERS = [
    (3, Decimal("0.0000"), Decimal("50.00")),
    (6, Decimal("0.1000"), Decimal("50.00")),
    (12, Decimal("0.1500"), Decimal("50.00")),
    (24, Decimal("0.3000"), Decimal("500.00")),
]


def ensure_plan_offers(db: Session) -> None:
    """Insert any missing default offers. Safe to call on every startup."""
    existing = set(db.scalars(select(PlanOffer.term_months)))
    for term, apr, min_amount in DEFAULT_OFFERS:
        if term not in existing:
            db.add(PlanOffer(term_months=term, apr=apr, min_amount=min_amount))
    db.flush()


def check_financeable(amount: Decimal) -> None:
    if not MIN_FINANCED_AMOUNT <= amount <= MAX_FINANCED_AMOUNT:
        raise AppError(
            422,
            "AMOUNT_OUT_OF_RANGE",
            f"Only purchases between ${MIN_FINANCED_AMOUNT} and ${MAX_FINANCED_AMOUNT} can be financed.",
        )


def available_offers(db: Session, amount: Decimal) -> list[PlanOffer]:
    stmt = select(PlanOffer).where(PlanOffer.min_amount <= amount).order_by(PlanOffer.term_months)
    return list(db.scalars(stmt))


def default_autopay_day(today: date) -> int:
    return min(today.day, 28)


@dataclass(frozen=True)
class PlanQuote:
    term_months: int
    apr: Decimal
    monthly_payment: Decimal
    total_interest: Decimal
    total_cost: Decimal


def quote(amount: Decimal, offer: PlanOffer, today: date) -> PlanQuote:
    schedule = build_schedule(amount, offer.apr, offer.term_months, today, default_autopay_day(today))
    return PlanQuote(
        term_months=offer.term_months,
        apr=offer.apr,
        monthly_payment=schedule.monthly_payment,
        total_interest=schedule.total_interest,
        total_cost=schedule.total_cost,
    )


def build_plan(*, user_id: int, transaction_id: int, offer: PlanOffer, principal: Decimal,
               autopay_day: int, now: datetime) -> Plan:
    """Create an (unsaved) Plan with its full installment schedule."""
    schedule = build_schedule(principal, offer.apr, offer.term_months, now.date(), autopay_day)
    return Plan(
        user_id=user_id,
        transaction_id=transaction_id,
        offer_id=offer.id,
        term_months=offer.term_months,
        apr=offer.apr,
        principal=principal,
        monthly_payment=schedule.monthly_payment,
        total_interest=schedule.total_interest,
        amount_paid=Decimal("0.00"),
        autopay_day=autopay_day,
        status=PlanStatus.active,
        created_at=now,
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
    return AppError(409, "PLAN_ALREADY_SELECTED", "A plan has already been selected for this transaction.")


def select_plan(db: Session, transaction: Transaction, term_months: int, autopay_day: int | None = None,
                now: datetime | None = None) -> Plan:
    """Create the plan and schedule, and mark the transaction financed. Flushes but doesn't commit."""
    if transaction.status != TransactionStatus.pending_plan:
        raise _already_selected()

    offers = {offer.term_months: offer for offer in available_offers(db, transaction.amount)}
    offer = offers.get(term_months)
    if offer is None:
        terms = ", ".join(str(term) for term in sorted(offers))
        raise AppError(422, "INVALID_TERM", f"{term_months}-month plan isn't available for this purchase. "
                                             f"Available terms: {terms}.")

    now = now or utcnow()
    plan = build_plan(
        user_id=transaction.consumer_id,
        transaction_id=transaction.id,
        offer=offer,
        principal=transaction.amount,
        autopay_day=autopay_day or default_autopay_day(now.date()),
        now=now,
    )
    db.add(plan)
    transaction.status = TransactionStatus.financed
    transaction.service_fee = to_cents(transaction.amount * SERVICE_FEE_RATE)
    try:
        db.flush()
    except IntegrityError:
        # Another request created a plan for this transaction first (unique plans.transaction_id).
        db.rollback()
        raise _already_selected()
    return plan


def change_autopay_day(plan: Plan, autopay_day: int) -> None:
    """Move the due date of every installment that isn't fully paid to the new day of the month."""
    if plan.status == PlanStatus.paid_off:
        raise AppError(409, "PLAN_PAID_OFF", "This plan is already paid off.")
    plan.autopay_day = autopay_day
    start = plan.created_at.date()
    for installment in plan.installments:
        if installment.status != InstallmentStatus.paid:
            installment.due_date = add_months(start, installment.seq, autopay_day)
