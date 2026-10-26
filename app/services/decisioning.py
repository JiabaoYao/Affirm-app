"""Underwriting: mock soft credit check -> risk tier -> approve / review / decline a checkout."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    CreditCheck,
    Plan,
    PlanStatus,
    RiskTier,
    TierDecision,
    Transaction,
    TransactionStatus,
    User,
    utcnow,
)

D = Decimal

# (name, min_score, max_score, decision, apr, max_amount, max_term_months)
DEFAULT_TIERS = [
    ("A", 740, 850, TierDecision.approve, D("0.1000"), D("15000.00"), 24),
    ("B", 680, 739, TierDecision.approve, D("0.1800"), D("7500.00"), 24),
    ("C", 640, 679, TierDecision.approve, D("0.2800"), D("2500.00"), 12),
    ("D", 600, 639, TierDecision.review, D("0.3000"), D("1500.00"), 12),
    ("E", 300, 599, TierDecision.decline, D("0.3000"), D("0.00"), 0),
]

MIN_SCORE, MAX_SCORE = 300, 850


def ensure_risk_tiers(db: Session) -> None:
    """Insert any missing default tiers. Safe to call on every startup; never overwrites admin edits."""
    existing = set(db.scalars(select(RiskTier.name)))
    for name, lo, hi, decision, apr, max_amount, max_term in DEFAULT_TIERS:
        if name not in existing:
            db.add(RiskTier(name=name, min_score=lo, max_score=hi, decision=decision, apr=apr,
                            max_amount=max_amount, max_term_months=max_term))
    db.flush()


def mock_score(email: str) -> int:
    """Deterministic fake bureau score in 560-820, so the same person always gets the same answer."""
    digest = hashlib.sha256(email.lower().encode()).hexdigest()
    return 560 + int(digest, 16) % 261


def tier_for(db: Session, score: int) -> RiskTier:
    tier = db.scalar(select(RiskTier).where(RiskTier.min_score <= score, RiskTier.max_score >= score))
    if tier is None:
        raise AppError(500, "NO_RISK_TIER", f"No risk tier covers score {score}.")
    return tier


def run_credit_check(db: Session, user: User, *, score: int | None = None, now: datetime | None = None) -> CreditCheck:
    """New soft check. Without an explicit score, the mock bureau returns the score it gave last time."""
    if score is None:
        previous = latest_credit_check(db, user.id)
        score = previous.score if previous else mock_score(user.email)
    check = CreditCheck(user_id=user.id, score=score, tier=tier_for(db, score), created_at=now or utcnow())
    db.add(check)
    db.flush()
    return check


def latest_credit_check(db: Session, user_id: int) -> CreditCheck | None:
    stmt = (select(CreditCheck).where(CreditCheck.user_id == user_id)
            .order_by(CreditCheck.created_at.desc(), CreditCheck.id.desc()).limit(1))
    return db.scalar(stmt)


def outstanding_balance(db: Session, user_id: int) -> Decimal:
    """What the consumer still owes on live or pending loans; it reduces their spending power."""
    plans = db.scalars(select(Plan).where(
        Plan.user_id == user_id, Plan.status.in_([PlanStatus.pending_capture, PlanStatus.active])
    ))
    return sum((p.remaining_balance for p in plans), D("0.00"))


@dataclass(frozen=True)
class SpendingPower:
    check: CreditCheck
    outstanding: Decimal

    @property
    def available(self) -> Decimal:
        if self.check.tier.decision == TierDecision.decline:
            return D("0.00")
        return max(self.check.tier.max_amount - self.outstanding, D("0.00"))


def spending_power(db: Session, check: CreditCheck) -> SpendingPower:
    return SpendingPower(check=check, outstanding=outstanding_balance(db, check.user_id))


def decide(db: Session, tx: Transaction, check: CreditCheck, now: datetime | None = None) -> None:
    """Set tx.status to approved / in_review / declined, with the reason shown to the consumer."""
    tier = check.tier
    tx.credit_check_id = check.id
    tx.credit_check = check
    tx.decided_at = now or utcnow()
    power = spending_power(db, check)

    if tier.decision == TierDecision.decline:
        tx.status = TransactionStatus.declined
        tx.decision_reason = (f"Your credit score ({check.score}) is below the minimum we can currently "
                              f"approve for financing.")
    elif tx.amount > power.available:
        tx.status = TransactionStatus.declined
        tx.decision_reason = (f"This ${tx.amount} purchase is more than your available spending power of "
                              f"${power.available}.")
    elif not any(p.active and p.min_amount <= tx.amount <= p.max_amount and p.term_months <= tier.max_term_months
                 for p in tx.merchant.programs):
        tx.status = TransactionStatus.declined
        tx.decision_reason = "This merchant has no financing program for this purchase amount."
    elif tier.decision == TierDecision.review:
        tx.status = TransactionStatus.in_review
        tx.decision_reason = "Your application needs a quick manual review. We'll notify you when it's done."
    else:
        tx.status = TransactionStatus.approved
        tx.decision_reason = None
