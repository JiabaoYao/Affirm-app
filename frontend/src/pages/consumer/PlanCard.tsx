import { Link } from "react-router-dom";

import type { PlanSummary } from "../../api/types";
import { ProgressBar } from "../../components/loan";
import { StatusBadge } from "../../components/ui";
import { apr, date, item, money } from "../../lib/format";

export default function PlanCard({ plan }: { plan: PlanSummary }) {
  const total = Number(plan.principal) + Number(plan.total_interest);
  return (
    <Link to={`/app/loans/${plan.id}`} className="card block p-5 transition hover:border-brand-300 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-900">{item(plan)}</p>
          <p className="text-sm text-slate-500">{plan.merchant_name}</p>
        </div>
        {plan.days_past_due > 0 ? (
          <StatusBadge status="overdue" label={`${plan.days_past_due} days overdue`} />
        ) : (
          <StatusBadge status={plan.status} />
        )}
      </div>
      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs text-slate-500">Remaining</p>
          <p className="text-xl font-bold">{money(plan.remaining_balance)}</p>
        </div>
        <div className="text-right text-sm">
          <p className="font-semibold">{money(plan.monthly_payment)}/mo</p>
          <p className="text-slate-500">
            {plan.term_months} mo · {apr(plan.apr)} APR
          </p>
        </div>
      </div>
      <div className="mt-3">
        <ProgressBar paid={Number(plan.amount_paid)} total={total} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {plan.status === "active" && plan.next_due_date && (
          <>
            Next payment {date(plan.next_due_date)}
            {plan.autopay_enabled ? " · Autopay on" : " · Autopay off"}
          </>
        )}
        {plan.status === "pending_capture" && "Starts when the merchant ships your order"}
        {plan.status === "paid_off" && "Paid in full 🎉"}
        {plan.status === "voided" && "Order cancelled by the merchant. Nothing owed."}
      </p>
    </Link>
  );
}
