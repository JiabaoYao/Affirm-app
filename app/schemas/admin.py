from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import MerchantStatus, TierDecision
from app.schemas.common import ORMModel

RateIn = Annotated[Decimal, Field(ge=0, le=1, max_digits=5, decimal_places=4)]


class AdminMerchantOut(ORMModel):
    user_id: int
    email: str
    full_name: str
    business_name: str
    status: MerchantStatus
    fee_rate: Decimal
    promo_fee_rate: Decimal
    created_at: datetime
    reviewed_at: datetime | None


class MerchantDecisionIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"fee_rate": "0.0300"}]})

    fee_rate: RateIn | None = None
    promo_fee_rate: RateIn | None = None


class RiskTierOut(ORMModel):
    id: int
    name: str
    min_score: int
    max_score: int
    decision: TierDecision
    apr: Decimal
    max_amount: Decimal
    max_term_months: int


class RiskTierUpdate(BaseModel):
    """Score bands are fixed, so tiers never overlap or leave gaps. Everything else is editable."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"apr": "0.2500", "max_term_months": 12}]})

    decision: TierDecision | None = None
    apr: RateIn | None = None
    max_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    max_term_months: Literal[0, 3, 6, 12, 24] | None = None


class DelinquentLoanOut(BaseModel):
    plan_id: int
    customer_email: str
    customer_name: str
    merchant_name: str
    product_name: str
    remaining_balance: Decimal
    overdue_amount: Decimal
    days_past_due: int
    bucket: str
    next_due_date: date | None
    autopay_enabled: bool


class MetricsOut(BaseModel):
    applications: int
    approved: int = Field(description="Approved at decision time, including those that went on to a plan")
    declined: int
    in_review: int
    approval_rate: Decimal
    active_loans: int
    outstanding_balance: Decimal
    delinquent_loans: int
    delinquency_rate: Decimal
    captured_volume: Decimal
    fee_revenue: Decimal
    pending_merchants: int
    statuses: dict[str, int]


class RunDailyIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"as_of": "2026-11-15"}]})

    as_of: date | None = Field(default=None, description="Simulated business date. Defaults to today.")


class RunDailyOut(BaseModel):
    as_of: date
    autopay_payments: int
    autopay_amount: Decimal
    reminders: int
    overdue_notices: int


class AuditLogOut(ORMModel):
    id: int
    actor_email: str
    action: str
    entity: str
    entity_id: int
    details: dict[str, Any]
    created_at: datetime
