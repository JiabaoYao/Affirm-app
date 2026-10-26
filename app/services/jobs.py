"""The daily servicing job: autopay, due-soon reminders and overdue notices. Triggered by an admin for the demo."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstallmentStatus, PaymentSource, Plan, PlanStatus
from app.services.events import notify
from app.services.payments import apply_payment

REMINDER_DAYS = 3


@dataclass
class DailyRunResult:
    as_of: date
    autopay_payments: int = 0
    autopay_amount: Decimal = Decimal("0.00")
    reminders: int = 0
    overdue_notices: int = 0


def run_daily(db: Session, as_of: date) -> DailyRunResult:
    """Idempotent: an installment that was paid or notified isn't paid or notified again. Flushes, doesn't commit."""
    result = DailyRunResult(as_of=as_of)
    paid_at = datetime.combine(as_of, time(9), tzinfo=timezone.utc)
    # of=Plan: Postgres can't lock the outer-joined (eager-loaded) tables, and only plans are written.
    plans = db.scalars(select(Plan).where(Plan.status == PlanStatus.active).with_for_update(of=Plan)).all()

    for plan in plans:
        link = f"/app/loans/{plan.id}"
        unpaid = [i for i in plan.installments if i.status != InstallmentStatus.paid]

        if plan.autopay_enabled and plan.payment_method_id is not None:
            due = sum((i.amount_remaining for i in unpaid if i.due_date <= as_of), Decimal("0.00"))
            if due > 0:
                apply_payment(plan, due, paid_at, payment_method_id=plan.payment_method_id,
                              source=PaymentSource.autopay)
                result.autopay_payments += 1
                result.autopay_amount += due
                notify(db, plan.user_id, "autopay", "Autopay payment processed",
                       f"We charged ${due} for your {plan.product_name} plan. Remaining balance: "
                       f"${plan.remaining_balance}.", link=link)
                continue

        for inst in unpaid:
            if inst.due_date < as_of:
                if notify(db, plan.user_id, "overdue", "Payment overdue",
                          f"Your ${inst.amount_remaining} payment for {plan.product_name} was due "
                          f"{inst.due_date:%b %d}. Pay now to get back on track.",
                          link=link, dedupe_key=f"overdue:{inst.id}"):
                    result.overdue_notices += 1
            elif inst.due_date <= as_of + timedelta(days=REMINDER_DAYS) and not plan.autopay_enabled:
                if notify(db, plan.user_id, "due_soon", "Payment due soon",
                          f"${inst.amount_remaining} for {plan.product_name} is due {inst.due_date:%b %d}.",
                          link=link, dedupe_key=f"due:{inst.id}"):
                    result.reminders += 1
    db.flush()
    return result
