import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  useCancelTransactionMutation,
  useGetTransactionQuery,
  usePlanOptionsQuery,
  useSelectPlanMutation,
} from "../../api/transactionsApi";
import type { PlanOption, Transaction } from "../../api/types";
import { usePaymentMethodsQuery } from "../../api/walletApi";
import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { MethodSelect, PaymentMethodForm } from "../../components/loan";
import { Alert, ErrorState, Spinner, StatusBadge } from "../../components/ui";
import {
  agreementToggled,
  autopayDayChanged,
  autopayToggled,
  checkoutStarted,
  paymentMethodChosen,
  stepChanged,
  termChosen,
} from "../../features/checkout/checkoutSlice";
import { toastAdded } from "../../features/ui/toastSlice";
import { apr, date, item, money, ordinal } from "../../lib/format";

const STEPS = ["Decision", "Choose plan", "Review & sign", "Done"];

function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-center gap-2 text-xs font-medium sm:text-sm">
      {STEPS.map((label, i) => (
        <li key={label} className="flex flex-1 items-center gap-2">
          <span
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
              i < current ? "bg-brand-600 text-white" : i === current ? "bg-brand-100 text-brand-700 ring-2 ring-brand-600" : "bg-slate-100 text-slate-400"
            }`}
          >
            {i < current ? "✓" : i + 1}
          </span>
          <span className={`hidden sm:inline ${i <= current ? "text-slate-900" : "text-slate-400"}`}>{label}</span>
          {i < STEPS.length - 1 && <span className="h-px flex-1 bg-slate-200" />}
        </li>
      ))}
    </ol>
  );
}

function OrderSummary({ tx }: { tx: Transaction }) {
  return (
    <aside className="card h-fit p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Your order</p>
      <p className="mt-2 font-semibold">{item(tx)}</p>
      <p className="text-sm text-slate-500">{tx.merchant_name}</p>
      {tx.quantity > 1 && (
        <p className="mt-2 text-sm text-slate-600">
          {tx.quantity} × {money(Number(tx.amount) / tx.quantity)}
        </p>
      )}
      <p className="mt-3 text-2xl font-bold">{money(tx.amount)}</p>
      {tx.credit_score !== null && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Soft credit check: score <strong>{tx.credit_score}</strong>, tier <strong>{tx.risk_tier}</strong>. Your credit score isn't affected.
        </p>
      )}
    </aside>
  );
}

function OfferCard({ option, selected, onSelect }: { option: PlanOption; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={`card w-full p-5 text-left transition hover:border-brand-400 ${selected ? "border-brand-600 ring-2 ring-brand-600" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-2xl font-bold">
            {money(option.monthly_payment)}
            <span className="text-base font-medium text-slate-500">/mo</span>
          </p>
          <p className="text-sm text-slate-600">for {option.term_months} months</p>
        </div>
        {option.zero_apr_promo ? (
          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">0% APR</span>
        ) : (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{apr(option.apr)} APR</span>
        )}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-sm">
        <dt className="text-slate-500">Interest</dt>
        <dd className="text-right font-medium">{money(option.total_interest)}</dd>
        <dt className="text-slate-500">Total cost</dt>
        <dd className="text-right font-semibold">{money(option.total_cost)}</dd>
      </dl>
    </button>
  );
}

function firstDueDate(day: number): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() + 1, day);
  return date(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
}

function PlanStep({ tx }: { tx: Transaction }) {
  const dispatch = useAppDispatch();
  const termMonths = useAppSelector((s) => s.checkout.termMonths);
  const { data, isLoading, error, refetch } = usePlanOptionsQuery(tx.id);
  const [cancel, { isLoading: cancelling }] = useCancelTransactionMutation();
  const navigate = useNavigate();

  if (isLoading) return <Spinner label="Pricing your plans…" />;
  if (error || !data) return <ErrorState error={error} onRetry={refetch} />;

  return (
    <div>
      <Alert kind="success">
        <strong>You're approved!</strong> Choose how you'd like to pay for {item(tx)}. No fees, and the total is fixed upfront.
      </Alert>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {data.options.map((o) => (
          <OfferCard key={o.term_months} option={o} selected={o.term_months === termMonths} onSelect={() => dispatch(termChosen(o.term_months))} />
        ))}
      </div>
      <button
        className="btn-ghost mt-6"
        disabled={cancelling}
        onClick={async () => {
          await cancel(tx.id).unwrap().catch(() => undefined);
          navigate("/app/shop");
        }}
      >
        Cancel this purchase
      </button>
    </div>
  );
}

function ReviewStep({ tx }: { tx: Transaction }) {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const state = useAppSelector((s) => s.checkout);
  const { data: options } = usePlanOptionsQuery(tx.id);
  const { data: methods = [], isLoading: loadingMethods } = usePaymentMethodsQuery();
  const [selectPlan, { isLoading }] = useSelectPlanMutation();
  const option = options?.options.find((o) => o.term_months === state.termMonths);

  // Default to the user's default payment method once methods load.
  useEffect(() => {
    if (state.paymentMethodId === null && methods.length > 0) {
      dispatch(paymentMethodChosen((methods.find((m) => m.is_default) ?? methods[0]).id));
    }
  }, [dispatch, methods, state.paymentMethodId]);

  // E.g. a reload on the review step after the offers changed: go back and pick again.
  useEffect(() => {
    if (options && !option) dispatch(stepChanged("plans"));
  }, [dispatch, options, option]);

  if (!option) return <Spinner />;

  async function submit() {
    try {
      const plan = await selectPlan({
        id: tx.id,
        body: {
          term_months: option!.term_months,
          autopay_day: state.autopayDay,
          autopay_enabled: state.autopayEnabled && methods.length > 0,
          payment_method_id: state.paymentMethodId ?? undefined,
          agree: state.agreed,
        },
      }).unwrap();
      dispatch(stepChanged("done"));
      dispatch(toastAdded("success", "Loan agreement signed. We'll let you know when your order ships."));
      navigate(`/app/loans/${plan.id}`, { replace: true });
    } catch {
      // toast from the global handler
    }
  }

  return (
    // A div, not a <form>: the add-payment-method form inside must not submit the loan agreement.
    <div className="space-y-5">
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Your plan</h2>
          <button className="text-sm font-semibold text-brand-700 hover:underline" onClick={() => dispatch(stepChanged("plans"))}>
            Change
          </button>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-500">Monthly payment</dt>
          <dd className="text-right font-semibold">
            {money(option.monthly_payment)} × {option.term_months}
          </dd>
          <dt className="text-slate-500">APR</dt>
          <dd className="text-right">{option.zero_apr_promo ? "0% (paid by the merchant)" : apr(option.apr)}</dd>
          <dt className="text-slate-500">Interest</dt>
          <dd className="text-right">{money(option.total_interest)}</dd>
          <dt className="text-slate-500">Total of payments</dt>
          <dd className="text-right font-semibold">{money(option.total_cost)}</dd>
          <dt className="text-slate-500">First payment</dt>
          <dd className="text-right">{firstDueDate(state.autopayDay)}</dd>
        </dl>
      </div>

      <div className="card space-y-4 p-5">
        <h2 className="font-semibold">Payments</h2>
        {loadingMethods ? (
          <Spinner />
        ) : methods.length === 0 ? (
          <div className="space-y-3">
            <Alert kind="warning">Add a bank account or debit card for autopay. You can also skip it and pay manually.</Alert>
            <PaymentMethodForm compact onAdded={(m) => dispatch(paymentMethodChosen(m.id))} />
          </div>
        ) : (
          <div>
            <label className="label" htmlFor="checkout-method">
              Pay from
            </label>
            <MethodSelect id="checkout-method" methods={methods} value={state.paymentMethodId} onChange={(id) => dispatch(paymentMethodChosen(id))} />
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand-600"
              checked={state.autopayEnabled && methods.length > 0}
              disabled={methods.length === 0}
              onChange={(e) => dispatch(autopayToggled(e.target.checked))}
            />
            <span>
              <strong>Autopay</strong> each month (recommended)
            </span>
          </label>
          <div>
            <label className="label" htmlFor="autopay-day">
              Payment day of the month
            </label>
            <select id="autopay-day" className="input" value={state.autopayDay} onChange={(e) => dispatch(autopayDayChanged(Number(e.target.value)))}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>
                  {ordinal(d)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="card space-y-3 p-5 text-sm">
        <h2 className="font-semibold">Loan agreement</h2>
        <div className="max-h-40 overflow-y-auto rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
          <p>
            You agree to repay {money(tx.amount)} for your {item(tx)} from {tx.merchant_name} in {option.term_months} monthly payments of about{" "}
            {money(option.monthly_payment)}, at an annual percentage rate (APR) of {apr(option.apr)}. The total of payments is {money(option.total_cost)},
            including {money(option.total_interest)} of simple interest.
          </p>
          <p className="mt-2">
            There are no late fees and no prepayment penalty. You can pay extra or pay the loan off at any time. Payments begin once the merchant
            ships your order. If the merchant cancels the order, the loan is cancelled and you owe nothing.
          </p>
          <p className="mt-2">This is a simulated agreement for a demo application. No real credit is extended.</p>
        </div>
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600"
            checked={state.agreed}
            onChange={(e) => dispatch(agreementToggled(e.target.checked))}
          />
          <span>I've read the loan agreement and agree to the terms above.</span>
        </label>
      </div>

      <button className="btn-primary w-full py-3 text-base" onClick={submit} disabled={!state.agreed || isLoading}>
        {isLoading ? "Signing…" : `Confirm and pay ${money(option.monthly_payment)}/mo`}
      </button>
    </div>
  );
}

function Outcome({ tx }: { tx: Transaction }) {
  const [cancel, { isLoading }] = useCancelTransactionMutation();
  if (tx.status === "declined") {
    return (
      <div className="card p-6">
        <StatusBadge status="declined" />
        <h2 className="mt-3 text-xl font-bold">We couldn't approve this purchase</h2>
        <p className="mt-2 text-sm text-slate-600">{tx.decision_reason}</p>
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          This decision came from a soft credit check, which doesn't affect your credit score. You can pay the merchant directly or try a smaller
          purchase.
        </p>
        <Link to="/app/shop" className="btn-secondary mt-5">
          Back to the store
        </Link>
      </div>
    );
  }
  if (tx.status === "in_review") {
    return (
      <div className="card p-6">
        <StatusBadge status="in_review" />
        <h2 className="mt-3 text-xl font-bold">Your application is being reviewed</h2>
        <p className="mt-2 text-sm text-slate-600">{tx.decision_reason}</p>
        <p className="mt-2 text-sm text-slate-600">This page updates on its own when the review is done.</p>
        <div className="mt-5 flex gap-2">
          <Link to="/app" className="btn-secondary">
            Back to home
          </Link>
          <button className="btn-ghost" disabled={isLoading} onClick={() => cancel(tx.id)}>
            Cancel application
          </button>
        </div>
      </div>
    );
  }
  if (tx.status === "cancelled") {
    return (
      <div className="card p-6">
        <StatusBadge status="cancelled" />
        <h2 className="mt-3 text-xl font-bold">You cancelled this purchase</h2>
        <Link to="/app/shop" className="btn-secondary mt-5">
          Back to the store
        </Link>
      </div>
    );
  }
  return (
    <div className="card p-6">
      <StatusBadge status={tx.status} />
      <h2 className="mt-3 text-xl font-bold">
        {tx.status === "authorized" ? "You're all set!" : tx.status === "captured" ? "Your order has shipped" : "This order was cancelled"}
      </h2>
      <p className="mt-2 text-sm text-slate-600">
        {tx.status === "authorized" && `Your plan starts when ${tx.merchant_name} ships your ${item(tx)}.`}
        {tx.status === "captured" && "Your plan is active."}
        {tx.status === "voided" && "The merchant cancelled the order, so you owe nothing."}
      </p>
      {tx.plan_id && (
        <Link to={`/app/loans/${tx.plan_id}`} className="btn-primary mt-5">
          View my loan
        </Link>
      )}
    </div>
  );
}

export default function Checkout() {
  const id = Number(useParams().id);
  const dispatch = useAppDispatch();
  const step = useAppSelector((s) => s.checkout.step);
  // While under review, poll so the shopper sees the admin's decision without refreshing.
  const { data: tx, isLoading, error, refetch } = useGetTransactionQuery(id, { skip: !id });
  const reviewing = tx?.status === "in_review";
  useGetTransactionQuery(id, { skip: !reviewing, pollingInterval: 5000 });

  useEffect(() => {
    if (id) dispatch(checkoutStarted(id));
  }, [dispatch, id]);

  if (isLoading) return <Spinner label="Checking your application…" />;
  if (error || !tx) return <ErrorState error={error} onRetry={refetch} />;

  const choosing = tx.status === "approved";
  const current = choosing ? (step === "review" ? 2 : 1) : ["authorized", "captured"].includes(tx.status) ? 3 : 0;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Checkout with Affirm</h1>
      <Stepper current={current} />
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div>{choosing ? step === "review" ? <ReviewStep tx={tx} /> : <PlanStep tx={tx} /> : <Outcome tx={tx} />}</div>
        <OrderSummary tx={tx} />
      </div>
    </div>
  );
}
