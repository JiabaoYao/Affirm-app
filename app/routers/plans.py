from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import ConsumerUser, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import Payment, Plan, PlanStatus, User
from app.schemas.common import Page
from app.schemas.plan import PaymentIn, PaymentOut, PaymentResult, PlanDetail, PlanSummary, PlanUpdate
from app.services.payments import apply_payment
from app.services.plans import change_autopay_day

router = APIRouter(prefix="/plans", tags=["Plans"])


def _get_own_plan(db: Session, plan_id: int, consumer: User, *, lock: bool = False) -> Plan:
    stmt = select(Plan).where(Plan.id == plan_id, Plan.user_id == consumer.id)
    if lock:
        # Row lock until commit: serializes concurrent writes to the same plan.
        stmt = stmt.with_for_update()
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
    status: PlanStatus | None = None,
    sort: Literal["created_at", "-created_at"] = "-created_at",
) -> Page[PlanSummary]:
    stmt = select(Plan).where(Plan.user_id == consumer.id)
    if status is not None:
        stmt = stmt.where(Plan.status == status)
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
    summary="Change the autopay day (consumer)",
    description="Moves the due date of every installment that isn't fully paid to the new day of the month.",
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_plan(plan_id: int, body: PlanUpdate, consumer: ConsumerUser, db: DbSession) -> Plan:
    plan = _get_own_plan(db, plan_id, consumer, lock=True)
    change_autopay_day(plan, body.autopay_day)
    db.commit()
    return plan


@router.post(
    "/{plan_id}/payments",
    status_code=201,
    response_model=PaymentResult,
    summary="Make a payment (consumer)",
    description="Applied to the oldest unpaid installment first; any extra spills into the next ones. "
                "The plan becomes `paid_off` when the balance reaches zero.",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
def make_payment(plan_id: int, body: PaymentIn, consumer: ConsumerUser, db: DbSession) -> PaymentResult:
    plan = _get_own_plan(db, plan_id, consumer, lock=True)
    payment = apply_payment(plan, body.amount)
    db.commit()
    return PaymentResult(
        id=payment.id,
        plan_id=plan.id,
        amount=payment.amount,
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
