from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import InstallmentStatus, PaymentSource, PlanStatus
from app.schemas.common import MoneyIn, ORMModel


class InstallmentOut(ORMModel):
    seq: int
    due_date: date
    amount_due: Decimal
    principal: Decimal
    interest: Decimal
    amount_paid: Decimal
    status: InstallmentStatus
    days_past_due: int


class PlanSummary(ORMModel):
    id: int
    transaction_id: int
    product_name: str
    quantity: int
    merchant_name: str
    term_months: int
    apr: Decimal
    zero_apr_promo: bool
    principal: Decimal
    monthly_payment: Decimal
    total_interest: Decimal
    amount_paid: Decimal
    remaining_balance: Decimal
    autopay_day: int
    autopay_enabled: bool
    payment_method_id: int | None
    next_due_date: date | None
    days_past_due: int
    overdue_amount: Decimal
    status: PlanStatus
    agreement_accepted_at: datetime | None
    created_at: datetime
    activated_at: datetime | None


class PlanDetail(PlanSummary):
    installments: list[InstallmentOut]


class PlanUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"autopay_day": 1, "autopay_enabled": True}]})

    autopay_day: int | None = Field(default=None, ge=1, le=28, description="New payment day of month (1-28)")
    autopay_enabled: bool | None = None
    payment_method_id: int | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "PlanUpdate":
        if self.autopay_day is None and self.autopay_enabled is None and self.payment_method_id is None:
            raise ValueError("Provide autopay_day, autopay_enabled or payment_method_id")
        return self


class PaymentIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"amount": "150.00", "payment_method_id": 1}]})

    amount: MoneyIn
    payment_method_id: int | None = Field(default=None, description="Defaults to your default payment method")


class PaymentOut(ORMModel):
    id: int
    plan_id: int
    amount: Decimal
    payment_method_id: int | None
    source: PaymentSource
    paid_at: datetime


class PaymentResult(PaymentOut):
    remaining_balance: Decimal
    plan_status: PlanStatus
