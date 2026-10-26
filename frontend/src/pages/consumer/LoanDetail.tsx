import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { useGetPlanQuery, useListPaymentsQuery, useMakePaymentMutation, useUpdatePlanMutation } from "../../api/plansApi";
import type { PlanDetail } from "../../api/types";
import { usePaymentMethodsQuery } from "../../api/walletApi";
import { useAppDispatch } from "../../app/hooks";
import { MethodSelect, methodLabel, ProgressBar, ScheduleTable } from "../../components/loan";
import { Alert, ErrorState, Modal, Spinner, StatCard, StatusBadge, TableCard } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { getErrorMessage, getHttpStatus } from "../../lib/errors";
import { apr, date, dateTime, item, money, ordinal } from "../../lib/format";

function PaymentModal({ plan, open, onClose }: { plan: PlanDetail; open: boolean; onClose: () => void }) {
  const { data: methods = [] } = usePaymentMethodsQuery();
  const [pay, { isLoading, error, reset }] = useMakePaymentMutation();
  const dispatch = useAppDispatch();
  const next = plan.installments.find((i) => i.status !== "paid");
  const nextDue = next ? (Number(next.amount_due) - Number(next.amount_paid)).toFixed(2) : "0.00";
  const presets = [
    ...(Number(plan.overdue_amount) > 0 ? [{ label: "Past due amount", amount: plan.overdue_amount }] : []),
    { label: "Next installment", amount: nextDue },
    { label: "Pay off loan", amount: plan.remaining_balance },
  ];
  const [amount, setAmount] = useState(presets[0].amount);
  const [methodId, setMethodId] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setAmount(presets[0].amount);
      setMethodId(plan.payment_method_id ?? methods.find((m) => m.is_default)?.id ?? null);
      reset();
    }
  }, [open]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const result = await pay({ id: plan.id, amount, payment_method_id: methodId ?? undefined }).unwrap();
      dispatch(
        toastAdded(
          "success",
          result.plan_status === "paid_off" ? "Loan paid off! 🎉" : `Payment of ${money(result.amount)} received. ${money(result.remaining_balance)} left.`,
        ),
      );
      onClose();
    } catch {
      // shown below
    }
  }

  return (
    <Modal open={open} title="Make a payment" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-2">
          {presets.map((p) => (
            <label key={p.label} className={`flex cursor-pointer items-center justify-between rounded-xl border px-4 py-3 text-sm ${amount === p.amount ? "border-brand-600 bg-brand-50" : "border-slate-200"}`}>
              <span className="flex items-center gap-3">
                <input type="radio" name="preset" checked={amount === p.amount} onChange={() => setAmount(p.amount)} className="text-brand-600" />
                {p.label}
              </span>
              <strong>{money(p.amount)}</strong>
            </label>
          ))}
        </div>
        <div>
          <label className="label" htmlFor="pay-amount">
            Amount
          </label>
          <input
            id="pay-amount"
            className="input"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            pattern="^\d+(\.\d{1,2})?$"
            title="A dollar amount like 25 or 25.50"
            required
          />
          <p className="mt-1 text-xs text-slate-500">Extra payments go to the next installments. There's never a prepayment fee.</p>
        </div>
        {methods.length > 0 ? (
          <div>
            <label className="label" htmlFor="pay-method">
              Pay from
            </label>
            <MethodSelect id="pay-method" methods={methods} value={methodId} onChange={setMethodId} />
          </div>
        ) : (
          <Alert kind="warning">
            No payment method on file. <Link to="/app/wallet" className="font-semibold underline">Add one</Link> or continue with a one-time payment.
          </Alert>
        )}
        {/* Business errors (e.g. overpayment) arrive as a toast; only field validation is shown here. */}
        {getHttpStatus(error) === 422 && <Alert kind="error">{getErrorMessage(error)}</Alert>}
        <button className="btn-primary w-full py-2.5" disabled={isLoading}>
          {isLoading ? "Processing…" : `Pay ${money(amount || 0)}`}
        </button>
      </form>
    </Modal>
  );
}

function AutopayCard({ plan }: { plan: PlanDetail }) {
  const { data: methods = [] } = usePaymentMethodsQuery();
  const [update, { isLoading }] = useUpdatePlanMutation();
  const dispatch = useAppDispatch();
  const [day, setDay] = useState(plan.autopay_day);
  const [methodId, setMethodId] = useState<number | null>(plan.payment_method_id);
  const open = plan.status === "active" || plan.status === "pending_capture";
  const method = methods.find((m) => m.id === plan.payment_method_id);

  useEffect(() => {
    setDay(plan.autopay_day);
    setMethodId(plan.payment_method_id ?? methods.find((m) => m.is_default)?.id ?? null);
  }, [plan.autopay_day, plan.payment_method_id, methods]);

  async function save(body: Parameters<typeof update>[0]["body"], message: string) {
    try {
      await update({ id: plan.id, body }).unwrap();
      dispatch(toastAdded("success", message));
    } catch {
      // toast from the global handler
    }
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">Autopay</h2>
          <p className="text-sm text-slate-500">
            {plan.autopay_enabled ? `On · ${methodLabel(method)} · the ${ordinal(plan.autopay_day)} of each month` : "Off · you'll pay manually"}
          </p>
        </div>
        {open && (
          <button
            className={plan.autopay_enabled ? "btn-secondary" : "btn-primary"}
            disabled={isLoading || (!plan.autopay_enabled && methods.length === 0)}
            onClick={() =>
              save(
                { autopay_enabled: !plan.autopay_enabled, payment_method_id: methodId ?? undefined },
                plan.autopay_enabled ? "Autopay turned off." : "Autopay turned on.",
              )
            }
          >
            {plan.autopay_enabled ? "Turn off" : "Turn on"}
          </button>
        )}
      </div>
      {open && (
        <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div>
            <label className="label" htmlFor="plan-day">
              Payment day
            </label>
            <select id="plan-day" className="input" value={day} onChange={(e) => setDay(Number(e.target.value))}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>
                  {ordinal(d)} of the month
                </option>
              ))}
            </select>
          </div>
          {methods.length > 0 ? (
            <div>
              <label className="label" htmlFor="plan-method">
                Pay from
              </label>
              <MethodSelect id="plan-method" methods={methods} value={methodId} onChange={setMethodId} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              <Link to="/app/wallet" className="font-semibold text-brand-700 underline">
                Add a payment method
              </Link>{" "}
              to use autopay.
            </p>
          )}
          <button
            className="btn-secondary"
            disabled={isLoading || (day === plan.autopay_day && methodId === plan.payment_method_id)}
            onClick={() =>
              save(
                {
                  ...(day !== plan.autopay_day ? { autopay_day: day } : {}),
                  ...(methodId && methodId !== plan.payment_method_id ? { payment_method_id: methodId } : {}),
                },
                "Payment settings saved. Unpaid due dates moved.",
              )
            }
          >
            Save
          </button>
        </div>
      )}
    </div>
  );
}

export default function LoanDetail() {
  const id = Number(useParams().id);
  const { data: plan, isLoading, error, refetch } = useGetPlanQuery(id);
  const { data: payments = [] } = useListPaymentsQuery(id);
  const { data: methods = [] } = usePaymentMethodsQuery();
  const [paying, setPaying] = useState(false);

  if (isLoading) return <Spinner />;
  if (error || !plan) return <ErrorState error={error} onRetry={refetch} />;

  const total = Number(plan.principal) + Number(plan.total_interest);
  const methodById = new Map(methods.map((m) => [m.id, m]));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link to="/app/loans" className="text-sm font-semibold text-brand-700 hover:underline">
            ← My loans
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{item(plan)}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500">
            {plan.merchant_name} · {plan.term_months} months · {apr(plan.apr)} APR
            <StatusBadge status={plan.status} />
          </p>
        </div>
        {plan.status === "active" && (
          <button className="btn-primary px-6 py-2.5" onClick={() => setPaying(true)}>
            Make a payment
          </button>
        )}
      </div>

      {plan.days_past_due > 0 && (
        <Alert kind="error">
          <strong>{money(plan.overdue_amount)} is {plan.days_past_due} days past due.</strong> Paying now gets your loan back on track. Affirm never charges
          late fees.
        </Alert>
      )}
      {plan.status === "pending_capture" && (
        <Alert>Your plan starts when {plan.merchant_name} ships your order. Payments open after that. If the order is cancelled, you owe nothing.</Alert>
      )}
      {plan.status === "voided" && <Alert>This order was cancelled by the merchant, so the loan was cancelled. You owe nothing.</Alert>}
      {plan.status === "paid_off" && <Alert kind="success">Paid in full. Nice work! 🎉</Alert>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard tone="brand" label="Remaining balance" value={money(plan.remaining_balance)} hint={`${money(plan.amount_paid)} paid of ${money(total)}`} />
        <StatCard label="Next payment" value={plan.next_due_date && plan.status !== "voided" ? date(plan.next_due_date) : "—"} hint={`${money(plan.monthly_payment)} monthly`} />
        <StatCard label="Interest" value={money(plan.total_interest)} hint={plan.zero_apr_promo ? "0% APR promo" : `${apr(plan.apr)} APR, simple interest`} />
        <StatCard label="Purchase amount" value={money(plan.principal)} hint={`Signed ${date(plan.agreement_accepted_at)}`} />
      </div>
      <ProgressBar paid={Number(plan.amount_paid)} total={total} />

      <AutopayCard plan={plan} />

      <section>
        <h2 className="mb-3 text-lg font-semibold">Payment schedule</h2>
        <TableCard>
          <ScheduleTable installments={plan.installments} />
        </TableCard>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Payment history</h2>
        {payments.length === 0 ? (
          <p className="card p-5 text-sm text-slate-500">No payments yet.</p>
        ) : (
          <TableCard>
            <table className="table-base">
              <thead className="bg-slate-50">
                <tr>
                  <th>Date</th>
                  <th className="text-right">Amount</th>
                  <th>Method</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[...payments].reverse().map((p) => (
                  <tr key={p.id}>
                    <td>{dateTime(p.paid_at)}</td>
                    <td className="text-right font-medium">{money(p.amount)}</td>
                    <td>{p.payment_method_id ? methodLabel(methodById.get(p.payment_method_id)) : "One-time"}</td>
                    <td>
                      <StatusBadge status={p.source === "autopay" ? "approve" : "pending_capture"} label={p.source === "autopay" ? "Autopay" : "Manual"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
        )}
      </section>

      {plan.status === "active" && <PaymentModal plan={plan} open={paying} onClose={() => setPaying(false)} />}
    </div>
  );
}
