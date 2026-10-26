from fastapi import APIRouter

from app.core.deps import ConsumerUser, DbSession
from app.core.errors import AppError, error_responses
from app.models import CreditCheck
from app.schemas.account import CreditOut
from app.services.decisioning import latest_credit_check, run_credit_check, spending_power

router = APIRouter(prefix="/credit", tags=["Credit"])


def _to_out(db, check: CreditCheck) -> CreditOut:
    power = spending_power(db, check)
    tier = check.tier
    return CreditOut(
        score=check.score,
        risk_tier=tier.name,
        decision=tier.decision,
        apr=tier.apr,
        max_amount=tier.max_amount,
        max_term_months=tier.max_term_months,
        outstanding_balance=power.outstanding,
        spending_power=power.available,
        checked_at=check.created_at,
    )


@router.post(
    "/check",
    response_model=CreditOut,
    summary="Run a soft credit check (consumer)",
    description="Mock bureau pull that never affects the score, so it's always available. "
                "Returns the score, the risk tier and the spending power left after current loans.",
    responses=error_responses(401, 403),
)
def check_credit(consumer: ConsumerUser, db: DbSession) -> CreditOut:
    check = run_credit_check(db, consumer)
    out = _to_out(db, check)
    db.commit()
    return out


@router.get(
    "/me",
    response_model=CreditOut,
    summary="My latest credit check (consumer)",
    responses=error_responses(401, 403, 404),
)
def my_credit(consumer: ConsumerUser, db: DbSession) -> CreditOut:
    check = latest_credit_check(db, consumer.id)
    if check is None:
        raise AppError(404, "NO_CREDIT_CHECK", "You haven't checked your spending power yet.")
    return _to_out(db, check)
