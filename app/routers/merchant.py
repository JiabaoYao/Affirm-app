from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import ActiveMerchant, DbSession
from app.core.errors import AppError, error_responses
from app.models import MerchantProgram, Transaction, TransactionStatus, utcnow
from app.schemas.merchant import MerchantSummary, ProgramIn, ProgramOut, ProgramUpdate
from app.services.amortization import to_cents
from app.services.events import audit
from app.services.plans import MAX_FINANCED_AMOUNT, MIN_FINANCED_AMOUNT

router = APIRouter(prefix="/merchant", tags=["Merchant"])


def _check_limits(min_amount: Decimal, max_amount: Decimal) -> None:
    if min_amount > max_amount:
        raise AppError(422, "INVALID_RANGE", "min_amount must not be greater than max_amount.")
    if min_amount < MIN_FINANCED_AMOUNT or max_amount > MAX_FINANCED_AMOUNT:
        raise AppError(422, "AMOUNT_OUT_OF_RANGE", f"Programs must stay between ${MIN_FINANCED_AMOUNT} and "
                                                   f"${MAX_FINANCED_AMOUNT}.")


@router.get("/programs", response_model=list[ProgramOut], summary="My financing programs (merchant)",
            responses=error_responses(401, 403))
def list_programs(merchant: ActiveMerchant, db: DbSession) -> list[MerchantProgram]:
    return list(db.scalars(select(MerchantProgram).where(MerchantProgram.merchant_id == merchant.id)
                           .order_by(MerchantProgram.term_months)))


@router.post(
    "/programs",
    status_code=201,
    response_model=ProgramOut,
    summary="Offer a new term at checkout (merchant)",
    description="Each term (3, 6, 12, 24 months) can be offered once. A 0% APR promo is merchant-funded: "
                "the promo fee is added to the merchant fee on those orders.",
    responses=error_responses(401, 403, 409, 422),
)
def create_program(body: ProgramIn, merchant: ActiveMerchant, db: DbSession) -> MerchantProgram:
    _check_limits(body.min_amount, body.max_amount)
    program = MerchantProgram(merchant_id=merchant.id, term_months=body.term_months,
                              zero_apr_promo=body.zero_apr_promo, min_amount=body.min_amount,
                              max_amount=body.max_amount, active=body.active, created_at=utcnow())
    db.add(program)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "PROGRAM_EXISTS", f"You already offer a {body.term_months}-month program. Edit it instead.")
    audit(db, merchant, "program.create", "program", program.id, term=program.term_months,
          promo=program.zero_apr_promo)
    db.commit()
    return program


@router.patch(
    "/programs/{program_id}",
    response_model=ProgramOut,
    summary="Change or pause a program (merchant)",
    description="Applies to new checkouts only. Existing loans keep the terms they were signed with.",
    responses=error_responses(401, 403, 404, 422),
)
def update_program(program_id: int, body: ProgramUpdate, merchant: ActiveMerchant, db: DbSession) -> MerchantProgram:
    program = db.scalar(select(MerchantProgram).where(MerchantProgram.id == program_id,
                                                      MerchantProgram.merchant_id == merchant.id))
    if program is None:
        raise AppError(404, "PROGRAM_NOT_FOUND", "Program not found.")
    changes = body.model_dump(exclude_none=True)
    _check_limits(changes.get("min_amount", program.min_amount), changes.get("max_amount", program.max_amount))
    for field, value in changes.items():
        setattr(program, field, value)
    audit(db, merchant, "program.update", "program", program.id, **changes)
    db.commit()
    return program


@router.get(
    "/summary",
    response_model=MerchantSummary,
    summary="Sales, fees and payouts (merchant)",
    description="Affirm pays the merchant upfront when an order is captured: amount minus the merchant fee.",
    responses=error_responses(401, 403),
)
def summary(merchant: ActiveMerchant, db: DbSession) -> MerchantSummary:
    rows = db.execute(
        select(Transaction.status, func.count(), func.coalesce(func.sum(Transaction.amount), 0),
               func.coalesce(func.sum(Transaction.merchant_fee), 0))
        .where(Transaction.merchant_id == merchant.id).group_by(Transaction.status)
    ).all()
    # str() first: SQLite (tests) returns sums as floats.
    by_status = {status: (count, to_cents(Decimal(str(amount))), to_cents(Decimal(str(fee))))
                 for status, count, amount, fee in rows}
    captured = by_status.get(TransactionStatus.captured, (0, Decimal(0), Decimal(0)))
    authorized = by_status.get(TransactionStatus.authorized, (0, Decimal(0), Decimal(0)))
    gross, fees = captured[1], captured[2]
    profile = merchant.merchant_profile
    return MerchantSummary(
        business_name=profile.business_name,
        fee_rate=profile.fee_rate,
        promo_fee_rate=profile.promo_fee_rate,
        gross_volume=gross,
        fees=fees,
        net_payout=gross - fees,
        awaiting_capture_amount=authorized[1],
        counts={s.value: by_status.get(s, (0,))[0] for s in TransactionStatus},
    )
