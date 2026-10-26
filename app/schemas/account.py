"""Consumer account: credit check, payment methods, notifications."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PaymentMethodKind, TierDecision
from app.schemas.common import ORMModel, Page


class CreditOut(BaseModel):
    score: int
    risk_tier: str
    decision: TierDecision = Field(description="What the risk rules do for this score: approve, review or decline")
    apr: Decimal = Field(description="APR for non-promo plans")
    max_amount: Decimal
    max_term_months: int
    outstanding_balance: Decimal
    spending_power: Decimal = Field(description="max_amount minus what you still owe")
    checked_at: datetime


class PaymentMethodIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"kind": "bank", "label": "Chase Checking", "last4": "1234"}]})

    kind: PaymentMethodKind
    label: str = Field(min_length=1, max_length=60)
    last4: str = Field(pattern=r"^\d{4}$", description="Last 4 digits only. Full numbers are never stored.")
    is_default: bool = False


class PaymentMethodOut(ORMModel):
    id: int
    kind: PaymentMethodKind
    label: str
    last4: str
    is_default: bool
    created_at: datetime


class NotificationOut(ORMModel):
    id: int
    kind: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(Page[NotificationOut]):
    unread: int
