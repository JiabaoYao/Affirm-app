from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import ConsumerUser, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import Payment, Plan, PlanStatus, User
from app.routers.transactions import get_payment_method
from app.schemas.common import Page
from app.schemas.plan import PaymentIn, PaymentOut, PaymentResult, PlanDetail, PlanSummary, PlanUpdate
from app.services.events import notify
from app.services.payments import apply_payment
from app.services.plans import change_autopay_day, set_autopay

router = APIRouter(prefix="/plans", tags=["Plans"])


def _get_own_plan(db: Session, plan_id: int, consumer: User, *, lock: bool = False) -> Plan:
    stmt = select(Plan).where(Plan.id == plan_id, Plan.user_id == consumer.id)
    if lock:
        # Row lock until commit: serializes concurrent writes to the same plan.
        # of=Plan because Postgres can't lock the outer-joined eager-loaded tables.
        stmt = stmt.with_for_update(of=Plan)
    plan = db.scalar(stmt)
    if plan is None:
        raise AppError(404, "PLAN_NOT_FOUND", "Plan not found.")
    return plan


@router.get(
    "",
    response_model=Page[PlanSummary],
    summary="List my installment plans (consumer)",
    responses=error_responses(401, 403, 422),
)
def list_plans(
    consumer: ConsumerUser,
    db: DbSession,
    pagination: Pagination,
    status: Annotated[list[PlanStatus] | None, Query(description="Repeat to match several")] = None,
    sort: Literal["created_at", "-created_at"] = "-created_at", # sort by creation date, default descending
) -> Page[PlanSummary]:
    # stmt is a Select object, a Python description of a SQL query.
    stmt = select(Plan).where(Plan.user_id == consumer.id)
    if status:
        stmt = stmt.where(Plan.status.in_(status))
    if sort.startswith("-"):
        stmt = stmt.order_by(Plan.created_at.desc(), Plan.id.desc())
    else:
        stmt = stmt.order_by(Plan.created_at.asc(), Plan.id.asc())
    items, total = paginate(db, stmt, pagination)
    return Page[PlanSummary](
        items=[PlanSummary.model_validate(p) for p in items], total=total, page=pagination.page, size=pagination.size
    )


@router.get(
    "/{plan_id}",
    response_model=PlanDetail,
    summary="Plan detail with full payment schedule (consumer)",
    responses=error_responses(401, 403, 404),
)
def get_plan(plan_id: int, consumer: ConsumerUser, db: DbSession) -> Plan:
    return _get_own_plan(db, plan_id, consumer)


@router.patch(
    "/{plan_id}",
    response_model=PlanDetail,
    summary="Change the payment day or autopay settings (consumer)",
    description="A new `autopay_day` moves the due date of every installment that isn't fully paid. "
                "Turning autopay on needs a payment method (yours by id, or your default).",
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_plan(plan_id: int, body: PlanUpdate, consumer: ConsumerUser, db: DbSession) -> Plan:
    plan = _get_own_plan(db, plan_id, consumer, lock=True)
    if body.autopay_day is not None:
        change_autopay_day(plan, body.autopay_day)
    if body.autopay_enabled is not None or body.payment_method_id is not None:
        method = get_payment_method(db, consumer.id, body.payment_method_id or plan.payment_method_id)
        enabled = plan.autopay_enabled if body.autopay_enabled is None else body.autopay_enabled
        set_autopay(plan, enabled, method)
    db.commit()
    return plan


@router.post(
    "/{plan_id}/payments",
    status_code=201,
    response_model=PaymentResult,
    summary="Make a payment (consumer)",
    description="Applied to the oldest unpaid installment first; any extra spills into the next ones. "
                "Paying the whole remaining balance pays the loan off early, with no fee. "
                "Only `active` plans (captured orders) take payments.",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
def make_payment(plan_id: int, body: PaymentIn, consumer: ConsumerUser, db: DbSession) -> PaymentResult:
    plan = _get_own_plan(db, plan_id, consumer, lock=True)
    method = get_payment_method(db, consumer.id, body.payment_method_id)
    payment = apply_payment(plan, body.amount, payment_method_id=method.id if method else None)
    if plan.status == PlanStatus.paid_off:
        notify(db, consumer.id, "paid_off", "Loan paid off!",
               f"Your {plan.product_name} plan is fully paid. Nice work.", link=f"/app/loans/{plan.id}")
    else:
        notify(db, consumer.id, "payment", "Payment received",
               f"We received ${body.amount} for {plan.product_name}. Remaining balance: ${plan.remaining_balance}.",
               link=f"/app/loans/{plan.id}")
    db.commit()
    return PaymentResult(
        id=payment.id,
        plan_id=plan.id,
        amount=payment.amount,
        payment_method_id=payment.payment_method_id,
        source=payment.source,
        paid_at=payment.paid_at,
        remaining_balance=plan.remaining_balance,
        plan_status=plan.status,
    )


@router.get(
    "/{plan_id}/payments",
    response_model=list[PaymentOut],
    summary="Payment history for a plan (consumer)",
    responses=error_responses(401, 403, 404),
)
def list_payments(plan_id: int, consumer: ConsumerUser, db: DbSession) -> list[Payment]:
    return _get_own_plan(db, plan_id, consumer).payments
