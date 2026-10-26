"""Internal operator console: merchant onboarding, risk rules, manual review, delinquency, servicing jobs."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import AdminUser, DbSession
from app.core.errors import AppError, error_responses
from app.core.pagination import Pagination, paginate
from app.models import (
    AuditLog,
    MerchantProfile,
    MerchantStatus,
    Plan,
    PlanStatus,
    RiskTier,
    Transaction,
    TransactionStatus,
    today,
    utcnow,
)
from app.routers.transactions import to_out
from app.schemas.admin import (
    AdminMerchantOut,
    AuditLogOut,
    DelinquentLoanOut,
    MerchantDecisionIn,
    MetricsOut,
    RiskTierOut,
    RiskTierUpdate,
    RunDailyIn,
    RunDailyOut,
)
from app.schemas.common import Page
from app.schemas.transaction import ReviewDecisionIn, TransactionOut
from app.services.amortization import to_cents
from app.services.events import audit, notify
from app.services.jobs import run_daily

router = APIRouter(prefix="/admin", tags=["Admin"])

Bucket = Literal["1-30", "31-60", "60+"]

# Decided "yes" at checkout, whatever happened after.
_APPROVED = (TransactionStatus.approved, TransactionStatus.authorized, TransactionStatus.captured,
             TransactionStatus.voided, TransactionStatus.cancelled)


def bucket_for(days_past_due: int) -> Bucket:
    if days_past_due <= 30:
        return "1-30"
    return "31-60" if days_past_due <= 60 else "60+"


def _ratio(part: int, whole: int) -> Decimal:
    return (Decimal(part) / whole).quantize(Decimal("0.0001")) if whole else Decimal("0.0000")


# ---------- Merchants ----------

def _get_merchant(db, merchant_id: int) -> MerchantProfile:
    profile = db.get(MerchantProfile, merchant_id)
    if profile is None:
        raise AppError(404, "MERCHANT_NOT_FOUND", "Merchant not found.")
    return profile


@router.get("/merchants", response_model=Page[AdminMerchantOut], summary="Merchant applications and accounts",
            responses=error_responses(401, 403, 422))
def list_merchants(admin: AdminUser, db: DbSession, pagination: Pagination,
                   status: MerchantStatus | None = None) -> Page[AdminMerchantOut]:
    stmt = select(MerchantProfile)
    if status is not None:
        stmt = stmt.where(MerchantProfile.status == status)
    stmt = stmt.order_by(MerchantProfile.created_at.desc(), MerchantProfile.user_id.desc())
    items, total = paginate(db, stmt, pagination)
    return Page[AdminMerchantOut](items=[AdminMerchantOut.model_validate(m) for m in items], total=total,
                                  page=pagination.page, size=pagination.size)


@router.post("/merchants/{merchant_id}/approve", response_model=AdminMerchantOut,
             summary="Approve (or reinstate) a merchant, optionally setting its fee rates",
             responses=error_responses(401, 403, 404, 409, 422))
def approve_merchant(merchant_id: int, admin: AdminUser, db: DbSession,
                     body: MerchantDecisionIn = MerchantDecisionIn()) -> MerchantProfile:
    profile = _get_merchant(db, merchant_id)
    if profile.status == MerchantStatus.active:
        raise AppError(409, "ALREADY_ACTIVE", "This merchant is already active.")
    if body.fee_rate is not None:
        profile.fee_rate = body.fee_rate
    if body.promo_fee_rate is not None:
        profile.promo_fee_rate = body.promo_fee_rate
    profile.status = MerchantStatus.active
    profile.reviewed_at = utcnow()
    audit(db, admin, "merchant.approve", "merchant", profile.user_id, fee_rate=profile.fee_rate)
    notify(db, profile.user_id, "merchant_approved", "Your merchant account is approved",
           f"{profile.business_name} can now offer Affirm at checkout. Set up your financing programs to start.",
           link="/merchant/programs")
    db.commit()
    return profile


@router.post("/merchants/{merchant_id}/suspend", response_model=AdminMerchantOut,
             summary="Suspend a merchant (hides its products, blocks new orders)",
             responses=error_responses(401, 403, 404, 409))
def suspend_merchant(merchant_id: int, admin: AdminUser, db: DbSession) -> MerchantProfile:
    profile = _get_merchant(db, merchant_id)
    if profile.status == MerchantStatus.suspended:
        raise AppError(409, "ALREADY_SUSPENDED", "This merchant is already suspended.")
    profile.status = MerchantStatus.suspended
    profile.reviewed_at = utcnow()
    audit(db, admin, "merchant.suspend", "merchant", profile.user_id)
    notify(db, profile.user_id, "merchant_suspended", "Your merchant account is suspended",
           "New Affirm checkouts are paused. Contact merchant support for details.")
    db.commit()
    return profile


# ---------- Risk rules ----------

@router.get("/risk-tiers", response_model=list[RiskTierOut], summary="Underwriting rules by credit score band",
            responses=error_responses(401, 403))
def list_tiers(admin: AdminUser, db: DbSession) -> list[RiskTier]:
    return list(db.scalars(select(RiskTier).order_by(RiskTier.min_score.desc())))


@router.patch("/risk-tiers/{tier_id}", response_model=RiskTierOut,
              summary="Change a tier's decision, APR, limit or max term",
              description="Applies to new checkouts only. Signed loans keep their APR.",
              responses=error_responses(401, 403, 404, 422))
def update_tier(tier_id: int, body: RiskTierUpdate, admin: AdminUser, db: DbSession) -> RiskTier:
    tier = db.get(RiskTier, tier_id)
    if tier is None:
        raise AppError(404, "TIER_NOT_FOUND", "Risk tier not found.")
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(tier, field, value)
    audit(db, admin, "risk_tier.update", "risk_tier", tier.id, tier=tier.name, **changes)
    db.commit()
    return tier


# ---------- Manual review ----------

def _get_review(db, transaction_id: int) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.id == transaction_id).with_for_update(of=Transaction))
    if tx is None:
        raise AppError(404, "TRANSACTION_NOT_FOUND", "Transaction not found.")
    if tx.status != TransactionStatus.in_review:
        raise AppError(409, "NOT_IN_REVIEW", "This application isn't waiting for review.")
    return tx


@router.get("/reviews", response_model=Page[TransactionOut], summary="Applications flagged for manual review",
            responses=error_responses(401, 403, 422))
def list_reviews(admin: AdminUser, db: DbSession, pagination: Pagination) -> Page[TransactionOut]:
    stmt = (select(Transaction).where(Transaction.status == TransactionStatus.in_review)
            .order_by(Transaction.created_at.asc(), Transaction.id.asc()))
    items, total = paginate(db, stmt, pagination)
    return Page[TransactionOut](items=[to_out(tx, admin) for tx in items], total=total, page=pagination.page,
                                size=pagination.size)


@router.post("/reviews/{transaction_id}/approve", response_model=TransactionOut,
             summary="Approve a flagged application", responses=error_responses(401, 403, 404, 409, 422))
def approve_review(transaction_id: int, admin: AdminUser, db: DbSession,
                   body: ReviewDecisionIn = ReviewDecisionIn()) -> TransactionOut:
    tx = _get_review(db, transaction_id)
    tx.status = TransactionStatus.approved
    tx.decision_reason = None
    tx.decided_at = utcnow()
    audit(db, admin, "review.approve", "transaction", tx.id, reason=body.reason or "")
    notify(db, tx.consumer_id, "review_approved", "You're approved!",
           f"Your {tx.product_name} application was approved. Choose your payment plan to finish checkout.",
           link=f"/app/checkout/{tx.id}")
    db.commit()
    return to_out(tx, admin)


@router.post("/reviews/{transaction_id}/decline", response_model=TransactionOut,
             summary="Decline a flagged application", description="`reason` is shown to the consumer.",
             responses=error_responses(401, 403, 404, 409, 422))
def decline_review(transaction_id: int, admin: AdminUser, db: DbSession,
                   body: ReviewDecisionIn = ReviewDecisionIn()) -> TransactionOut:
    tx = _get_review(db, transaction_id)
    tx.status = TransactionStatus.declined
    tx.decision_reason = body.reason or "We couldn't verify enough information to approve this purchase."
    tx.decided_at = utcnow()
    audit(db, admin, "review.decline", "transaction", tx.id, reason=tx.decision_reason)
    notify(db, tx.consumer_id, "review_declined", "Application not approved",
           f"Your {tx.product_name} application wasn't approved: {tx.decision_reason}",
           link=f"/app/checkout/{tx.id}")
    db.commit()
    return to_out(tx, admin)


# ---------- Portfolio ----------

def _active_plans(db) -> list[Plan]:
    return list(db.scalars(select(Plan).where(Plan.status == PlanStatus.active)))


@router.get("/delinquency", response_model=list[DelinquentLoanOut],
            summary="Overdue loans, most overdue first", responses=error_responses(401, 403, 422))
def delinquency(admin: AdminUser, db: DbSession, bucket: Bucket | None = None) -> list[DelinquentLoanOut]:
    rows = []
    for plan in _active_plans(db):
        dpd = plan.days_past_due
        if dpd == 0 or (bucket is not None and bucket_for(dpd) != bucket):
            continue
        tx = plan.transaction
        rows.append(DelinquentLoanOut(
            plan_id=plan.id, customer_email=tx.customer_email, customer_name=tx.customer_name,
            merchant_name=tx.merchant_name, product_name=tx.product_name,
            remaining_balance=plan.remaining_balance, overdue_amount=plan.overdue_amount,
            days_past_due=dpd, bucket=bucket_for(dpd), next_due_date=plan.next_due_date,
            autopay_enabled=plan.autopay_enabled,
        ))
    return sorted(rows, key=lambda r: -r.days_past_due)


@router.get("/metrics", response_model=MetricsOut, summary="Approval, portfolio and delinquency metrics",
            responses=error_responses(401, 403))
def metrics(admin: AdminUser, db: DbSession) -> MetricsOut:
    statuses = dict(db.execute(select(Transaction.status, func.count()).group_by(Transaction.status)).all())
    approved = sum(statuses.get(s, 0) for s in _APPROVED)
    declined = statuses.get(TransactionStatus.declined, 0)
    captured = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0), func.coalesce(func.sum(Transaction.merchant_fee), 0))
        .where(Transaction.status == TransactionStatus.captured)
    ).one()
    plans = _active_plans(db)
    delinquent = sum(1 for p in plans if p.days_past_due > 0)
    pending = db.scalar(select(func.count()).where(MerchantProfile.status == MerchantStatus.pending)) or 0
    return MetricsOut(
        applications=sum(statuses.values()),
        approved=approved,
        declined=declined,
        in_review=statuses.get(TransactionStatus.in_review, 0),
        approval_rate=_ratio(approved, approved + declined),
        active_loans=len(plans),
        outstanding_balance=sum((p.remaining_balance for p in plans), Decimal("0.00")),
        delinquent_loans=delinquent,
        delinquency_rate=_ratio(delinquent, len(plans)),
        # str() first: SQLite (tests) returns sums as floats.
        captured_volume=to_cents(Decimal(str(captured[0]))),
        fee_revenue=to_cents(Decimal(str(captured[1]))),
        pending_merchants=pending,
        statuses={s.value: statuses.get(s, 0) for s in TransactionStatus},
    )


# ---------- Servicing job & audit ----------

@router.post("/jobs/run-daily", response_model=RunDailyOut,
             summary="Run the daily servicing job (autopay, reminders, overdue notices)",
             description="Normally a scheduler runs this every morning. `as_of` simulates a business date, "
                         "e.g. a future date to see autopay charge due installments.",
             responses=error_responses(401, 403, 422))
def run_daily_job(admin: AdminUser, db: DbSession, body: RunDailyIn = RunDailyIn()) -> RunDailyOut:
    result = run_daily(db, body.as_of or today())
    audit(db, admin, "job.run_daily", "job", 0, as_of=result.as_of, autopay_payments=result.autopay_payments)
    db.commit()
    return RunDailyOut(**result.__dict__)


@router.get("/audit-log", response_model=Page[AuditLogOut], summary="Who changed what, newest first",
            responses=error_responses(401, 403, 422))
def audit_log(admin: AdminUser, db: DbSession, pagination: Pagination) -> Page[AuditLogOut]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    items, total = paginate(db, stmt, pagination)
    return Page[AuditLogOut](items=[AuditLogOut.model_validate(a) for a in items], total=total,
                             page=pagination.page, size=pagination.size)
