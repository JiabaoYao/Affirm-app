from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import TransactionStatus
from app.schemas.common import ORMModel


class TransactionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"customer_email": "alice@demo.com", "product_id": 2}]})

    customer_email: EmailStr = Field(description="Email of the consumer who is checking out")
    product_id: int


class TransactionOut(ORMModel):
    id: int
    consumer_id: int
    merchant_id: int
    product_id: int
    product_name: str
    amount: Decimal
    status: TransactionStatus
    service_fee: Decimal | None = Field(
        description="Fee the merchant pays Affirm once financed. Only returned to the merchant; null for consumers."
    )
    created_at: datetime


class PlanOptionOut(ORMModel):
    term_months: int
    apr: Decimal
    monthly_payment: Decimal
    total_interest: Decimal
    total_cost: Decimal


class PlanOptionsOut(BaseModel):
    transaction_id: int
    amount: Decimal
    options: list[PlanOptionOut]


class SelectPlanIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"term_months": 12, "autopay_day": 15}]})

    term_months: int = Field(description="One of the terms returned by /plan-options")
    autopay_day: int | None = Field(
        default=None, ge=1, le=28, description="Day of month for autopay (1-28). Defaults to today's day, capped at 28."
    )
