"""Pure amortization math: no database, so it is easy to unit test and reuse for quotes and real plans."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def add_months(start: date, months: int, day: int) -> date:
    """`day` of the month that is `months` after `start`. day is capped at 28, so every month has it."""
    index = start.month - 1 + months
    return date(start.year + index // 12, index % 12 + 1, day)

# @dataclass writes the boilerplate methods for you, based on the annotated fields
# frozen=True makes instances read-only after creation
@dataclass(frozen=True)
class ScheduleRow:
    seq: int
    due_date: date
    amount_due: Decimal
    principal: Decimal
    interest: Decimal


@dataclass(frozen=True)
class Schedule:
    monthly_payment: Decimal
    total_interest: Decimal
    rows: list[ScheduleRow]

    # @property makes a method look like an attribute
    @property
    def total_cost(self) -> Decimal:
        return sum((row.amount_due for row in self.rows), Decimal("0.00"))


def monthly_payment(principal: Decimal, apr: Decimal, term_months: int) -> Decimal:
    if apr == 0:
        return to_cents(principal / term_months)
    r = apr / 12
    return to_cents(principal * r / (1 - (1 + r) ** -term_months))


def build_schedule(principal: Decimal, apr: Decimal, term_months: int, start: date, autopay_day: int) -> Schedule:
    """Fixed-payment schedule. Interest accrues on the remaining balance each month, and the last
    installment pays off whatever balance is left, so rounding cents never leak."""
    payment = monthly_payment(principal, apr, term_months)
    r = apr / 12
    balance = principal
    rows: list[ScheduleRow] = []
    for seq in range(1, term_months + 1):
        interest = to_cents(balance * r)
        principal_part = balance if seq == term_months else payment - interest
        balance -= principal_part
        rows.append(
            ScheduleRow(
                seq=seq,
                due_date=add_months(start, seq, autopay_day),
                amount_due=principal_part + interest,
                principal=principal_part,
                interest=interest,
            )
        )
    total_interest = sum((row.interest for row in rows), Decimal("0.00"))
    return Schedule(monthly_payment=payment, total_interest=total_interest, rows=rows)
