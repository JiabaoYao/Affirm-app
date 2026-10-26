from datetime import timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.core.deps import ActiveMerchant, ConsumerUser, CurrentUser, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import (
    MerchantProfile,
    MerchantStatus,
    PaymentMethod,
    Plan,
    Product,
    Transaction,
    TransactionStatus,
    User,
    UserRole,
    as_utc,
    utcnow,
)
from app.schemas.common import Page
from app.schemas.plan import PlanDetail
from app.schemas.transaction import (
    PlanOptionOut,
    PlanOptionsOut,
    SelectPlanIn,
    TrackingUpdate,
    TransactionCreate,
    TransactionOut,
)
from app.services import orders
from app.services.decisioning import decide, latest_credit_check, run_credit_check
from app.services.events import audit, notify
from app.services.plans import quote, select_plan, tx_offers

router = APIRouter(prefix="/transactions", tags=["Transactions"])

_SORT_COLUMNS = {"created_at": Transaction.created_at, "amount": Transaction.amount}

# A soft check is reused for this long before checkout runs a fresh one.
CREDIT_CHECK_TTL = timedelta(days=30)


def _visible_to(user: User):
    """Merchants see their own orders, consumers their own purchases, admins everything."""
    if user.role == UserRole.admin:
        return true()
    if user.role == UserRole.merchant:
        return Transaction.merchant_id == user.id
    return Transaction.consumer_id == user.id


def _get_visible_transaction(db: Session, transaction_id: int, user: User, *, lock: bool = False) -> Transaction:
    stmt = select(Transaction).where(Transaction.id == transaction_id, _visible_to(user))
    if lock:
        stmt = stmt.with_for_update(of=Transaction)
    tx = db.scalar(stmt)
    if tx is None:
        # Same response whether it doesn't exist or belongs to someone else.
        raise AppError(404, "TRANSACTION_NOT_FOUND", "Transaction not found.")
    return tx


def to_out(tx: Transaction, user: User) -> TransactionOut:
    out = TransactionOut.model_validate(tx)
    if user.role == UserRole.merchant:
        # Like real Affirm, the merchant only learns approved/declined, never the consumer's credit data.
        out.decision_reason = out.credit_score = out.risk_tier = None
    if user.role == UserRole.consumer:
        out.merchant_fee = None  # merchant-Affirm data, hidden from consumers
    return out


def get_payment_method(db: Session, user_id: int, method_id: int | None) -> PaymentMethod | None:
    """The given method (404 if not the user's), else the user's default method, else None."""
    stmt = select(PaymentMethod).where(PaymentMethod.user_id == user_id, PaymentMethod.deleted_at.is_(None))
    if method_id is not None:
        method = db.scalar(stmt.where(PaymentMethod.id == method_id))
        if method is None:
            raise AppError(404, "PAYMENT_METHOD_NOT_FOUND", "Payment method not found.")
        return method
    return db.scalar(stmt.where(PaymentMethod.is_default.is_(True)))


@router.post(
    "",
    status_code=201,
    response_model=TransactionOut,
    summary="Check out with Affirm (consumer)",
    description="Starts a financed purchase of one product. Runs (or reuses) a soft credit check and decides "
                "right away: `approved` (see /plan-options), `in_review` (an admin decides) or `declined` "
                "(with `decision_reason`).",
    responses=error_responses(401, 403, 404, 422),
)
def create_transaction(body: TransactionCreate, consumer: ConsumerUser, db: DbSession) -> TransactionOut:
    product = db.scalar(
        select(Product).join(MerchantProfile, Product.merchant_id == MerchantProfile.user_id)
        .where(Product.id == body.product_id, MerchantProfile.status == MerchantStatus.active)
    )
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product not found.")

    now = utcnow()
    check = latest_credit_check(db, consumer.id)
    if check is None or as_utc(check.created_at) < now - CREDIT_CHECK_TTL:
        check = run_credit_check(db, consumer, now=now)

    tx = Transaction(
        consumer_id=consumer.id,
        merchant_id=product.merchant_id,
        merchant=product.merchant,
        consumer=consumer,
        product=product,
        amount=product.price,
        status=TransactionStatus.in_review,
        created_at=now,
    )
    decide(db, tx, check, now)
    db.add(tx)
    db.commit()
    return to_out(tx, consumer)


@router.get(
    "",
    response_model=Page[TransactionOut],
    summary="List my transactions (orders for merchants, all for admins)",
    responses=error_responses(401, 422),
)
def list_transactions(
    user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    status: Annotated[list[TransactionStatus] | None, Query(description="Repeat to match several")] = None,
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    sort: Literal["created_at", "-created_at", "amount", "-amount"] = "-created_at",
) -> Page[TransactionOut]:
    stmt = select(Transaction).where(_visible_to(user))
    if status:
        stmt = stmt.where(Transaction.status.in_(status))
    if min_amount is not None:
        stmt = stmt.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Transaction.amount <= max_amount)
    column = _SORT_COLUMNS[sort.lstrip("-")]
    if sort.startswith("-"):
        stmt = stmt.order_by(column.desc(), Transaction.id.desc())
    else:
        stmt = stmt.order_by(column.asc(), Transaction.id.asc())
    items, total = paginate(db, stmt, pagination)
    return Page[TransactionOut](
        items=[to_out(tx, user) for tx in items], total=total, page=pagination.page, size=pagination.size
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Transaction detail",
    responses=error_responses(401, 404),
)
def get_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> TransactionOut:
    return to_out(_get_visible_transaction(db, transaction_id, user), user)


@router.get(
    "/{transaction_id}/plan-options",
    response_model=PlanOptionsOut,
    summary="Compare the plans you're offered (consumer)",
    description="The merchant's programs that fit this amount and your risk tier, each with the monthly payment, "
                "total interest and total cost computed upfront, before you commit.",
    responses=error_responses(401, 403, 404, 409),
)
def get_plan_options(transaction_id: int, consumer: ConsumerUser, db: DbSession) -> PlanOptionsOut:
    tx = _get_visible_transaction(db, transaction_id, consumer)
    if tx.status != TransactionStatus.approved or tx.credit_check is None:
        raise AppError(409, "NOT_APPROVED", f"This purchase is {tx.status.value.replace('_', ' ')}, "
                                            f"so there are no plan options.")
    today = utcnow().date()
    options = [PlanOptionOut.model_validate(quote(tx.amount, offer, today)) for offer in tx_offers(tx)]
    return PlanOptionsOut(transaction_id=tx.id, amount=tx.amount, credit_score=tx.credit_check.score,
                          risk_tier=tx.credit_check.tier.name, options=options)


@router.post(
    "/{transaction_id}/plan",
    status_code=201,
    response_model=PlanDetail,
    summary="Accept the loan agreement for a plan (consumer)",
    description="Creates the installment plan and its full payment schedule and authorizes the order. "
                "The plan is `pending_capture` until the merchant ships; payments start after that.",
    responses=error_responses(401, 403, 404, 409, 422),
)
def choose_plan(transaction_id: int, body: SelectPlanIn, consumer: ConsumerUser, db: DbSession) -> Plan:
    tx = _get_visible_transaction(db, transaction_id, consumer, lock=True)
    method = get_payment_method(db, consumer.id, body.payment_method_id)
    plan = select_plan(db, tx, body.term_months, agree=body.agree, autopay_day=body.autopay_day,
                       autopay_enabled=body.autopay_enabled, payment_method=method)
    notify(db, tx.merchant_id, "order_authorized", "New Affirm order to ship",
           f"{tx.customer_name or tx.customer_email} bought {tx.product_name} (${tx.amount}). "
           f"Capture it when it ships.", link="/merchant/orders")
    db.commit()
    return plan


@router.post(
    "/{transaction_id}/cancel",
    response_model=TransactionOut,
    summary="Cancel a purchase before choosing a plan (consumer)",
    responses=error_responses(401, 403, 404, 409),
)
def cancel_transaction(transaction_id: int, consumer: ConsumerUser, db: DbSession) -> TransactionOut:
    tx = _get_visible_transaction(db, transaction_id, consumer, lock=True)
    orders.cancel(tx)
    db.commit()
    return to_out(tx, consumer)


@router.post(
    "/{transaction_id}/capture",
    response_model=TransactionOut,
    summary="Capture an order when it ships (merchant)",
    description="Activates the consumer's loan (payments can start) and books the merchant payout "
                "(amount minus fee).",
    responses=error_responses(401, 403, 404, 409),
)
def capture_transaction(transaction_id: int, merchant: ActiveMerchant, db: DbSession) -> TransactionOut:
    tx = _get_visible_transaction(db, transaction_id, merchant, lock=True)
    orders.capture(db, tx)
    audit(db, merchant, "order.capture", "transaction", tx.id, amount=tx.amount)
    db.commit()
    return to_out(tx, merchant)


@router.post(
    "/{transaction_id}/void",
    response_model=TransactionOut,
    summary="Void an order before it ships (merchant)",
    description="Cancels the authorization: the consumer's plan is voided and they owe nothing.",
    responses=error_responses(401, 403, 404, 409),
)
def void_transaction(transaction_id: int, merchant: ActiveMerchant, db: DbSession) -> TransactionOut:
    tx = _get_visible_transaction(db, transaction_id, merchant, lock=True)
    orders.void(db, tx)
    audit(db, merchant, "order.void", "transaction", tx.id, amount=tx.amount)
    db.commit()
    return to_out(tx, merchant)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Add shipment tracking (merchant)",
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_tracking(transaction_id: int, body: TrackingUpdate, merchant: ActiveMerchant,
                    db: DbSession) -> TransactionOut:
    tx = _get_visible_transaction(db, transaction_id, merchant, lock=True)
    if tx.status not in (TransactionStatus.authorized, TransactionStatus.captured):
        raise AppError(409, "INVALID_ORDER_STATE", "Tracking can only be added to authorized or captured orders.")
    tx.tracking_number = body.tracking_number.strip()
    db.commit()
    return to_out(tx, merchant)
