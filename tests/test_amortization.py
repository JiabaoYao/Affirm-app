from datetime import date
from decimal import Decimal

import pytest

from app.services.amortization import add_months, build_schedule

D = Decimal
START = date(2026, 10, 3)


def test_twelve_months_at_15_percent_matches_readme_example():
    schedule = build_schedule(D("1000.00"), D("0.15"), 12, START, 15)

    assert schedule.monthly_payment == D("90.26")
    assert schedule.total_interest == D("83.10")
    first, last = schedule.rows[0], schedule.rows[-1]
    assert (first.principal, first.interest, first.amount_due) == (D("77.76"), D("12.50"), D("90.26"))
    assert last.amount_due == D("90.24")  # last installment absorbs rounding


def test_zero_apr_splits_evenly_and_last_installment_takes_the_cent():
    schedule = build_schedule(D("1000.00"), D("0"), 3, START, 15)

    assert [row.amount_due for row in schedule.rows] == [D("333.33"), D("333.33"), D("333.34")]
    assert schedule.total_interest == D("0.00")


@pytest.mark.parametrize(
    ("term", "apr", "payment", "interest"),
    [(6, "0.10", "171.56", "29.36"), (24, "0.30", "55.91", "341.94")],
)
def test_other_offers_match_readme_quotes(term, apr, payment, interest):
    schedule = build_schedule(D("1000.00"), D(apr), term, START, 15)
    assert schedule.monthly_payment == D(payment)
    assert schedule.total_interest == D(interest)


@pytest.mark.parametrize("amount", ["50.00", "120.00", "999.99", "2400.00", "30000.00"])
@pytest.mark.parametrize(("term", "apr"), [(3, "0"), (6, "0.10"), (12, "0.15"), (24, "0.30")])
def test_schedule_always_balances_to_the_cent(amount, term, apr):
    principal = D(amount)
    schedule = build_schedule(principal, D(apr), term, START, 15)

    assert len(schedule.rows) == term
    assert sum(row.principal for row in schedule.rows) == principal
    assert schedule.total_cost == principal + schedule.total_interest
    assert all(row.amount_due == row.principal + row.interest for row in schedule.rows)
    assert all(row.principal > 0 for row in schedule.rows)


def test_due_dates_land_on_autopay_day_and_roll_over_the_year():
    schedule = build_schedule(D("1000.00"), D("0.15"), 12, START, 15)

    assert schedule.rows[0].due_date == date(2026, 11, 15)
    assert schedule.rows[2].due_date == date(2027, 1, 15)
    assert schedule.rows[-1].due_date == date(2027, 10, 15)


def test_add_months_december():
    assert add_months(date(2026, 12, 31), 1, 28) == date(2027, 1, 28)
    assert add_months(date(2026, 1, 1), 1, 28) == date(2026, 2, 28)
