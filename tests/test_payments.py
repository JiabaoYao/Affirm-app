from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.models import InstallmentStatus, PlanStatus
from app.services.payments import apply_payment
from app.services.plans import build_plan, change_autopay_day

D = Decimal
NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def make_plan(term=12, apr="0.15", principal="1000.00"):
    return build_plan(user_id=1, transaction_id=1, program_id=1, term_months=term, apr=D(apr), principal=D(principal),
                      autopay_day=15, now=NOW)


def statuses(plan):
    return [i.status for i in plan.installments]


def test_payment_fills_oldest_installment_then_spills_over():
    plan = make_plan()

    apply_payment(plan, D("150.00"), NOW)

    first, second = plan.installments[0], plan.installments[1]
    assert first.status == InstallmentStatus.paid and first.amount_paid == D("90.26")
    assert second.status == InstallmentStatus.partial and second.amount_paid == D("59.74")
    assert plan.amount_paid == D("150.00")
    assert plan.remaining_balance == D("933.10")
    assert plan.status == PlanStatus.active
    assert len(plan.payments) == 1


def test_overpayment_is_rejected_and_nothing_changes():
    plan = make_plan()

    with pytest.raises(AppError) as exc:
        apply_payment(plan, D("1083.11"), NOW)

    assert (exc.value.status_code, exc.value.code) == (400, "OVERPAYMENT")
    assert plan.amount_paid == D("0.00")
    assert plan.payments == []


def test_paying_exact_balance_pays_off_plan_and_further_payments_conflict():
    plan = make_plan()

    apply_payment(plan, plan.remaining_balance, NOW)

    assert plan.status == PlanStatus.paid_off
    assert plan.remaining_balance == 0
    assert set(statuses(plan)) == {InstallmentStatus.paid}
    with pytest.raises(AppError) as exc:
        apply_payment(plan, D("1.00"), NOW)
    assert (exc.value.status_code, exc.value.code) == (409, "PLAN_PAID_OFF")


def test_many_small_payments_reach_paid_off_exactly():
    plan = make_plan(term=3, apr="0", principal="100.00")  # 33.33, 33.33, 33.34

    for _ in range(9):
        apply_payment(plan, D("10.00"), NOW)
    assert plan.status == PlanStatus.active
    apply_payment(plan, plan.remaining_balance, NOW)

    assert plan.status == PlanStatus.paid_off
    assert [i.amount_paid for i in plan.installments] == [D("33.33"), D("33.33"), D("33.34")]


def test_changing_autopay_moves_only_unpaid_installments():
    plan = make_plan()
    apply_payment(plan, plan.installments[0].amount_due, NOW)
    paid_due = plan.installments[0].due_date

    change_autopay_day(plan, 1)

    assert plan.autopay_day == 1
    assert plan.installments[0].due_date == paid_due
    assert plan.installments[1].due_date.day == 1
    assert plan.installments[1].due_date.month == 12


def test_changing_autopay_on_paid_off_plan_conflicts():
    plan = make_plan()
    apply_payment(plan, plan.remaining_balance, NOW)

    with pytest.raises(AppError) as exc:
        change_autopay_day(plan, 5)
    assert exc.value.status_code == 409


def test_plan_waiting_for_capture_takes_no_payments():
    plan = make_plan()
    plan.status = PlanStatus.pending_capture

    with pytest.raises(AppError) as exc:
        apply_payment(plan, D("10.00"), NOW)
    assert (exc.value.status_code, exc.value.code) == (409, "PLAN_NOT_ACTIVE")
