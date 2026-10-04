from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import ConsumerUser, CurrentUser, DbSession, MerchantUser
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import Plan, Product, Transaction, TransactionStatus, User, UserRole, utcnow
from app.schemas.common import Page
from app.schemas.plan import PlanDetail
from app.schemas.transaction import (
    PlanOptionOut,
    PlanOptionsOut,
    SelectPlanIn,
    TransactionCreate,
    TransactionOut,
)
from app.services.plans import available_offers, check_financeable, quote, select_plan

router = APIRouter(prefix="/transactions", tags=["Transactions"])

_SORT_COLUMNS = {"created_at": Transaction.created_at, "amount": Transaction.amount}


def _visible_to(user: User):
    """Merchants see the checkouts they created; consumers see the purchases made for them."""
    if user.role == UserRole.merchant:
        return Transaction.merchant_id == user.id
    return Transaction.consumer_id == user.id


def _get_visible_transaction(db: Session, transaction_id: int, user: User) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.id == transaction_id, _visible_to(user)))
    if tx is None:
        # Same response whether it doesn't exist or belongs to someone else.
        raise AppError(404, "TRANSACTION_NOT_FOUND", "Transaction not found.")
    return tx


def _to_out(tx: Transaction, user: User) -> TransactionOut:
    out = TransactionOut.model_validate(tx)
    if user.role != UserRole.merchant:
        out.service_fee = None  # merchant-Affirm data, hidden from consumers
    return out


@router.post(
    "",
    status_code=201,
    response_model=TransactionOut,
    summary="Start a checkout for a consumer (merchant)",
    description="Records a purchase of one of the merchant's products for a consumer. "
                "The amount is copied from the product price; the purchase starts as `pending_plan`.",
    responses=error_responses(401, 403, 404, 422),
)
def create_transaction(body: TransactionCreate, merchant: MerchantUser, db: DbSession) -> TransactionOut:
    consumer = db.scalar(
        select(User).where(User.email == body.customer_email.lower(), User.role == UserRole.consumer)
    )
    if consumer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "No consumer account with this email.")
    product = db.scalar(select(Product).where(Product.id == body.product_id, Product.merchant_id == merchant.id))
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product not found.")
    check_financeable(product.price)

    tx = Transaction(
        consumer_id=consumer.id,
        merchant_id=merchant.id,
        product=product,
        amount=product.price,
        status=TransactionStatus.pending_plan,
        created_at=utcnow(),
    )
    db.add(tx)
    db.commit()
    return _to_out(tx, merchant)


@router.get(
    "",
    response_model=Page[TransactionOut],
    summary="List my transactions",
    responses=error_responses(401, 422),
)
def list_transactions(
    user: CurrentUser,
    db: DbSession,
    pagination: Pagination,
    status: TransactionStatus | None = None,
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    sort: Literal["created_at", "-created_at", "amount", "-amount"] = "-created_at",
) -> Page[TransactionOut]:
    stmt = select(Transaction).where(_visible_to(user))
    if status is not None:
        stmt = stmt.where(Transaction.status == status)
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
        items=[_to_out(tx, user) for tx in items], total=total, page=pagination.page, size=pagination.size
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionOut,
    summary="Transaction detail",
    responses=error_responses(401, 404),
)
def get_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> TransactionOut:
    return _to_out(_get_visible_transaction(db, transaction_id, user), user)


@router.get(
    "/{transaction_id}/plan-options",
    response_model=PlanOptionsOut,
    summary="Compare available plans (consumer)",
    description="Every plan offer available for this amount, with the monthly payment, total interest "
                "and total cost computed upfront, before the consumer commits.",
    responses=error_responses(401, 403, 404),
)
def get_plan_options(transaction_id: int, consumer: ConsumerUser, db: DbSession) -> PlanOptionsOut:
    tx = _get_visible_transaction(db, transaction_id, consumer)
    today = utcnow().date()
    options = [PlanOptionOut.model_validate(quote(tx.amount, offer, today)) for offer in available_offers(db, tx.amount)]
    return PlanOptionsOut(transaction_id=tx.id, amount=tx.amount, options=options)


@router.post(
    "/{transaction_id}/plan",
    status_code=201,
    response_model=PlanDetail,
    summary="Select a plan (consumer)",
    description="Creates the installment plan and its full payment schedule, and marks the purchase `financed`.",
    responses=error_responses(401, 403, 404, 409, 422),
)
def choose_plan(transaction_id: int, body: SelectPlanIn, consumer: ConsumerUser, db: DbSession) -> Plan:
    tx = _get_visible_transaction(db, transaction_id, consumer)
    plan = select_plan(db, tx, body.term_months, body.autopay_day)
    db.commit()
    return plan
