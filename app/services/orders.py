"""Order lifecycle after the decision: consumer cancel, merchant capture (ship) or void."""

from datetime import datetime

from app.core.errors import AppError
from app.models import PlanStatus, Transaction, TransactionStatus, utcnow
from app.services.events import notify


def _wrong_state(tx: Transaction, action: str) -> AppError:
    return AppError(409, "INVALID_ORDER_STATE", f"Can't {action} an order that is {tx.status.value.replace('_', ' ')}.")


def capture(db, tx: Transaction, now: datetime | None = None) -> None:
    """Merchant shipped the order: the loan becomes active and payments can start."""
    if tx.status != TransactionStatus.authorized or tx.plan is None:
        raise _wrong_state(tx, "capture")
    now = now or utcnow()
    tx.status = TransactionStatus.captured
    tx.captured_at = now
    tx.plan.status = PlanStatus.active
    tx.plan.activated_at = now
    notify(db, tx.consumer_id, "order_captured", f"{tx.merchant_name} shipped your {tx.product_name}",
           f"Your {tx.plan.term_months}-month plan is now active. First payment of ${tx.plan.monthly_payment} "
           f"is due {tx.plan.next_due_date:%b %d, %Y}.", link=f"/app/loans/{tx.plan.id}")


def void(db, tx: Transaction, now: datetime | None = None) -> None:
    """Merchant cancelled before shipping: the loan is cancelled and the consumer owes nothing."""
    if tx.status != TransactionStatus.authorized or tx.plan is None:
        raise _wrong_state(tx, "void")
    tx.status = TransactionStatus.voided
    tx.voided_at = now or utcnow()
    tx.merchant_fee = None
    tx.plan.status = PlanStatus.voided
    notify(db, tx.consumer_id, "order_voided", f"{tx.merchant_name} cancelled your order",
           f"Your {tx.product_name} order was cancelled, so your loan was cancelled too. You owe nothing.",
           link=f"/app/loans/{tx.plan.id}")


def cancel(tx: Transaction) -> None:
    """Consumer walks away before choosing a plan."""
    if tx.status not in (TransactionStatus.approved, TransactionStatus.in_review):
        raise _wrong_state(tx, "cancel")
    tx.status = TransactionStatus.cancelled
