from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import InstallmentStatus, PlanStatus
from app.schemas.common import MoneyIn, ORMModel


class InstallmentOut(ORMModel):
    seq: int
    due_date: date
    amount_due: Decimal
    principal: Decimal
    interest: Decimal
    amount_paid: Decimal
    status: InstallmentStatus


class PlanSummary(ORMModel):
    id: int
    transaction_id: int
    term_months: int
    apr: Decimal
    principal: Decimal
    monthly_payment: Decimal
    total_interest: Decimal
    amount_paid: Decimal
    remaining_balance: Decimal
    autopay_day: int
    next_due_date: date | None
    status: PlanStatus
    created_at: datetime


class PlanDetail(PlanSummary):
    installments: list[InstallmentOut]


class PlanUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"autopay_day": 1}]})

    autopay_day: int = Field(ge=1, le=28, description="New autopay day of month (1-28)")


class PaymentIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"amount": "150.00"}]})

    amount: MoneyIn


class PaymentOut(ORMModel):
    id: int
    plan_id: int
    amount: Decimal
    paid_at: datetime


class PaymentResult(PaymentOut):
    remaining_balance: Decimal
    plan_status: PlanStatus
