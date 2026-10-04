from datetime import datetime
from decimal import Decimal

from app.core.errors import AppError
from app.models import InstallmentStatus, Payment, Plan, PlanStatus, utcnow


def apply_payment(plan: Plan, amount: Decimal, now: datetime | None = None) -> Payment:
    """Apply `amount` to the oldest unpaid installments first, spilling into later ones.

    The caller must hold a row lock on the plan (SELECT ... FOR UPDATE) so concurrent
    payments can't both pass the balance check.
    """
    if plan.status == PlanStatus.paid_off:
        raise AppError(409, "PLAN_PAID_OFF", "This plan is already paid off.")
    remaining = plan.remaining_balance
    if amount > remaining:
        raise AppError(400, "OVERPAYMENT", f"Payment exceeds the remaining balance of ${remaining}.")

    left = amount
    for installment in plan.installments:
        if left == 0:
            break
        if installment.status == InstallmentStatus.paid:
            continue
        applied = min(left, installment.amount_remaining)
        installment.amount_paid += applied
        installment.status = InstallmentStatus.paid if installment.amount_remaining == 0 else InstallmentStatus.partial
        left -= applied

    plan.amount_paid += amount
    if plan.remaining_balance == 0:
        plan.status = PlanStatus.paid_off

    payment = Payment(amount=amount, paid_at=now or utcnow())
    plan.payments.append(payment)
    return payment
