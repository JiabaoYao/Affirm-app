from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import MoneyIn, ORMModel

Term = Literal[3, 6, 12, 24]


class ProgramIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [
        {"term_months": 6, "zero_apr_promo": True, "min_amount": "100.00", "max_amount": "5000.00"}
    ]})

    term_months: Term
    zero_apr_promo: bool = Field(default=False, description="Merchant-funded 0% APR (adds the promo fee)")
    min_amount: MoneyIn = Decimal("50.00")
    max_amount: MoneyIn = Decimal("30000.00")
    active: bool = True

    @model_validator(mode="after")
    def check_range(self) -> "ProgramIn":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount must not be greater than max_amount")
        return self


class ProgramUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"active": False}]})

    zero_apr_promo: bool | None = None
    min_amount: MoneyIn | None = None
    max_amount: MoneyIn | None = None
    active: bool | None = None


class ProgramOut(ORMModel):
    id: int
    term_months: int
    zero_apr_promo: bool
    min_amount: Decimal
    max_amount: Decimal
    active: bool
    created_at: datetime


class MerchantSummary(BaseModel):
    business_name: str
    fee_rate: Decimal
    promo_fee_rate: Decimal
    gross_volume: Decimal = Field(description="Captured order amounts")
    fees: Decimal = Field(description="Affirm fees on captured orders")
    net_payout: Decimal = Field(description="gross_volume - fees: what Affirm pays the merchant upfront")
    awaiting_capture_amount: Decimal
    counts: dict[str, int] = Field(description="Orders by status")
