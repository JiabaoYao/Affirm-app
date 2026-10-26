from fastapi import APIRouter, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import ConsumerUser, DbSession
from app.core.errors import AppError, error_responses
from app.models import PaymentMethod, Plan, User, utcnow
from app.schemas.account import PaymentMethodIn, PaymentMethodOut

router = APIRouter(prefix="/payment-methods", tags=["Payment methods"])

MAX_METHODS = 5


def _active(user: User):
    return select(PaymentMethod).where(PaymentMethod.user_id == user.id, PaymentMethod.deleted_at.is_(None))


def _get_own(db: Session, method_id: int, user: User) -> PaymentMethod:
    method = db.scalar(_active(user).where(PaymentMethod.id == method_id))
    if method is None:
        raise AppError(404, "PAYMENT_METHOD_NOT_FOUND", "Payment method not found.")
    return method


def _make_default(db: Session, user: User, method: PaymentMethod) -> None:
    db.execute(update(PaymentMethod).where(PaymentMethod.user_id == user.id).values(is_default=False))
    method.is_default = True


@router.get("", response_model=list[PaymentMethodOut], summary="My payment methods (consumer)",
            responses=error_responses(401, 403))
def list_methods(consumer: ConsumerUser, db: DbSession) -> list[PaymentMethod]:
    return list(db.scalars(_active(consumer).order_by(PaymentMethod.is_default.desc(), PaymentMethod.id)))


@router.post(
    "",
    status_code=201,
    response_model=PaymentMethodOut,
    summary="Add a bank account or debit card (consumer)",
    description="Mock: only a label and the last 4 digits are stored. The first method becomes the default.",
    responses=error_responses(401, 403, 409, 422),
)
def add_method(body: PaymentMethodIn, consumer: ConsumerUser, db: DbSession) -> PaymentMethod:
    existing = list(db.scalars(_active(consumer)))
    if len(existing) >= MAX_METHODS:
        raise AppError(409, "TOO_MANY_METHODS", f"You can save up to {MAX_METHODS} payment methods.")
    method = PaymentMethod(user_id=consumer.id, kind=body.kind, label=body.label.strip(), last4=body.last4,
                           is_default=False, created_at=utcnow())
    db.add(method)
    db.flush()
    if body.is_default or not existing:
        _make_default(db, consumer, method)
    db.commit()
    return method


@router.post("/{method_id}/default", response_model=PaymentMethodOut, summary="Make this my default (consumer)",
             responses=error_responses(401, 403, 404))
def set_default(method_id: int, consumer: ConsumerUser, db: DbSession) -> PaymentMethod:
    method = _get_own(db, method_id, consumer)
    _make_default(db, consumer, method)
    db.commit()
    return method


@router.delete(
    "/{method_id}",
    status_code=204,
    summary="Remove a payment method (consumer)",
    description="Plans that autopay from it switch to your default method, or turn autopay off if none is left.",
    responses=error_responses(401, 403, 404),
)
def remove_method(method_id: int, consumer: ConsumerUser, db: DbSession) -> Response:
    method = _get_own(db, method_id, consumer)
    method.deleted_at = utcnow()
    method.is_default = False
    db.flush()
    fallback = db.scalar(_active(consumer).order_by(PaymentMethod.id))
    if fallback is not None and not fallback.is_default:
        _make_default(db, consumer, fallback)
    for plan in db.scalars(select(Plan).where(Plan.payment_method_id == method.id)):
        plan.payment_method_id = fallback.id if fallback else None
        plan.autopay_enabled = plan.autopay_enabled and fallback is not None
    db.commit()
    return Response(status_code=204)
