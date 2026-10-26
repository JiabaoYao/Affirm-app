from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TransactionStatus
from app.schemas.common import ORMModel

MAX_QUANTITY = 10


class TransactionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"product_id": 2, "quantity": 1}]})

    product_id: int = Field(description="Product the consumer is buying with Affirm")
    quantity: int = Field(default=1, ge=1, le=MAX_QUANTITY, description=f"Units to buy (1-{MAX_QUANTITY})")


class TransactionOut(ORMModel):
    id: int
    consumer_id: int
    customer_email: str
    customer_name: str
    merchant_id: int
    merchant_name: str
    product_id: int
    product_name: str
    quantity: int
    amount: Decimal = Field(description="Total financed: unit price × quantity")
    status: TransactionStatus
    decision_reason: str | None = Field(description="Why it was declined or sent to review. Hidden from merchants.")
    credit_score: int | None = Field(description="Hidden from merchants.")
    risk_tier: str | None = Field(description="Hidden from merchants.")
    merchant_fee: Decimal | None = Field(description="Fee the merchant pays Affirm. Hidden from consumers.")
    tracking_number: str | None
    plan_id: int | None
    created_at: datetime
    decided_at: datetime | None
    captured_at: datetime | None
    voided_at: datetime | None


class TrackingUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"tracking_number": "1Z999AA10123456784"}]})

    tracking_number: str = Field(min_length=1, max_length=100)


class PlanOptionOut(ORMModel):
    term_months: int
    apr: Decimal
    zero_apr_promo: bool
    monthly_payment: Decimal
    total_interest: Decimal
    total_cost: Decimal


class PlanOptionsOut(BaseModel):
    transaction_id: int
    amount: Decimal
    credit_score: int
    risk_tier: str
    options: list[PlanOptionOut]


class SelectPlanIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [
        {"term_months": 12, "autopay_day": 15, "autopay_enabled": True, "payment_method_id": 1, "agree": True}
    ]})

    term_months: int = Field(description="One of the terms returned by /plan-options")
    autopay_day: int | None = Field(
        default=None, ge=1, le=28, description="Day of month for payments (1-28). Defaults to today's day, capped at 28."
    )
    autopay_enabled: bool = False
    payment_method_id: int | None = Field(default=None, description="Defaults to your default payment method")
    agree: bool = Field(description="The consumer accepted the loan agreement (APR, total cost, schedule)")


class ReviewDecisionIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"reason": "Verified identity and income."}]})

    reason: str | None = Field(default=None, max_length=255)
