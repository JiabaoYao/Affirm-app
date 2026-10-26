import { useCheckCreditMutation, useMyCreditQuery } from "../../api/storeApi";
import { useAppDispatch } from "../../app/hooks";
import { toastAdded } from "../../features/ui/toastSlice";
import { getErrorCode } from "../../lib/errors";
import { apr, dateTime, money } from "../../lib/format";

/** Credit score + spending power. The soft check is always available and never affects the score. */
export default function CreditCard({ compact = false }: { compact?: boolean }) {
  const { data, error, isLoading } = useMyCreditQuery();
  const [check, { isLoading: checking }] = useCheckCreditMutation();
  const dispatch = useAppDispatch();
  const neverChecked = getErrorCode(error) === "NO_CREDIT_CHECK";

  async function run() {
    try {
      const result = await check().unwrap();
      dispatch(toastAdded("success", `Your spending power is ${money(result.spending_power)}.`));
    } catch {
      // toast from the global handler
    }
  }

  if (isLoading) return <div className="card h-40 animate-pulse bg-slate-100" />;

  if (neverChecked || !data) {
    return (
      <div className="card bg-gradient-to-br from-brand-600 to-brand-800 p-6 text-white">
        <p className="text-sm font-semibold text-brand-100">Spending power</p>
        <p className="mt-2 text-xl font-bold">See how much you can spend</p>
        <p className="mt-1 text-sm text-brand-100">A soft credit check never affects your credit score.</p>
        <button className="btn mt-4 bg-white text-brand-700 hover:bg-brand-50" onClick={run} disabled={checking}>
          {checking ? "Checking…" : "Check my spending power"}
        </button>
      </div>
    );
  }

  const declined = data.decision === "decline";
  return (
    <div className="card bg-gradient-to-br from-brand-600 to-brand-800 p-6 text-white">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-brand-100">Spending power</p>
          <p className="mt-1 text-3xl font-bold tracking-tight">{money(data.spending_power)}</p>
          {!compact && (
            <p className="mt-1 text-xs text-brand-100">
              {money(data.max_amount)} limit · {money(data.outstanding_balance)} in use
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-brand-100">Credit score</p>
          <p className="mt-1 text-3xl font-bold">{data.score}</p>
          <p className="text-xs text-brand-100">Tier {data.risk_tier}</p>
        </div>
      </div>
      {!compact && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/20 pt-4 text-xs text-brand-100">
          <span>
            {declined
              ? "We can't approve financing at this score yet."
              : `Plans up to ${data.max_term_months} months · APR from ${apr(data.apr)} (0% where merchants offer it)`}
            {data.decision === "review" && " · New purchases get a quick manual review."}
          </span>
          <button className="rounded-full bg-white/15 px-3 py-1 font-semibold text-white hover:bg-white/25" onClick={run} disabled={checking}>
            {checking ? "Checking…" : `Refresh · checked ${dateTime(data.checked_at)}`}
          </button>
        </div>
      )}
    </div>
  );
}
