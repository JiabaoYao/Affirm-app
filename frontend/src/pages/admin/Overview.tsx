import { Link } from "react-router-dom";

import { useMetricsQuery } from "../../api/adminApi";
import type { TransactionStatus } from "../../api/types";
import { ErrorState, PageHeader, Spinner, StatCard } from "../../components/ui";
import { money, percent } from "../../lib/format";

interface StatusStyle {
  status: TransactionStatus;
  label: string;
  hint: string;
  color: string;
}

// Lifecycle order: the bar and the legend both read left to right, from application to loan, then exits.
const STATUS_GROUPS: { title: string; items: StatusStyle[] }[] = [
  {
    title: "In progress → financed",
    items: [
      { status: "in_review", label: "In review", hint: "waiting for an admin", color: "bg-amber-400" },
      { status: "approved", label: "Approved", hint: "shopper picking a plan", color: "bg-brand-400" },
      { status: "authorized", label: "Authorized", hint: "signed, awaiting shipment", color: "bg-sky-500" },
      { status: "captured", label: "Captured", hint: "shipped, loan active", color: "bg-emerald-500" },
    ],
  },
  {
    title: "Closed without a loan",
    items: [
      { status: "declined", label: "Declined", hint: "by the risk rules", color: "bg-rose-500" },
      { status: "cancelled", label: "Cancelled", hint: "by the shopper", color: "bg-slate-300" },
      { status: "voided", label: "Voided", hint: "by the merchant", color: "bg-slate-400" },
    ],
  },
];
const ALL_STATUSES = STATUS_GROUPS.flatMap((g) => g.items);

export default function AdminOverview() {
  const { data: m, isLoading, error, refetch } = useMetricsQuery(undefined, { pollingInterval: 20000 });
  if (isLoading) return <Spinner />;
  if (error || !m) return <ErrorState error={error} onRetry={refetch} />;
  const share = (status: TransactionStatus) => ((m.statuses[status] ?? 0) / Math.max(m.applications, 1)) * 100;

  return (
    <div className="space-y-8">
      <PageHeader title="Operations overview" subtitle="Underwriting, portfolio and merchant health across the platform." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard tone="brand" label="Outstanding balance" value={money(m.outstanding_balance)} hint={`${m.active_loans} active loans`} />
        <StatCard label="Approval rate" value={percent(m.approval_rate)} hint={`${m.approved} approved · ${m.declined} declined`} />
        <StatCard
          tone={m.delinquent_loans > 0 ? "danger" : "default"}
          label="Delinquency rate"
          value={percent(m.delinquency_rate)}
          hint={`${m.delinquent_loans} loan(s) past due`}
        />
        <StatCard label="Fee revenue" value={money(m.fee_revenue)} hint={`on ${money(m.captured_volume)} captured`} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Link to="/admin/reviews" className="card p-5 hover:border-brand-300">
          <p className="text-sm text-slate-500">Manual review queue</p>
          <p className="mt-1 text-3xl font-bold">{m.in_review}</p>
          <p className="mt-1 text-sm font-semibold text-brand-700">Review applications →</p>
        </Link>
        <Link to="/admin/merchants" className="card p-5 hover:border-brand-300">
          <p className="text-sm text-slate-500">Merchant applications</p>
          <p className="mt-1 text-3xl font-bold">{m.pending_merchants}</p>
          <p className="mt-1 text-sm font-semibold text-brand-700">Approve merchants →</p>
        </Link>
        <Link to="/admin/delinquency" className="card p-5 hover:border-brand-300">
          <p className="text-sm text-slate-500">Past-due loans</p>
          <p className="mt-1 text-3xl font-bold">{m.delinquent_loans}</p>
          <p className="mt-1 text-sm font-semibold text-brand-700">Open collections board →</p>
        </Link>
      </div>

      <section className="card p-5">
        <h2 className="font-semibold">Applications by status</h2>
        <p className="text-sm text-slate-500">{m.applications} checkouts in total</p>
        <div className="mt-4 flex h-4 overflow-hidden rounded-full bg-slate-100">
          {ALL_STATUSES.map(({ status, label, color }) =>
            m.statuses[status] ? (
              <div key={status} className={color} style={{ width: `${share(status)}%` }} title={`${label}: ${m.statuses[status]}`} />
            ) : null,
          )}
        </div>
        <div className="mt-5 space-y-4">
          {STATUS_GROUPS.map((group) => (
            <div key={group.title}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{group.title}</p>
              <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {group.items.map(({ status, label, hint, color }) => (
                  <li key={status} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                    <span className={`h-3 w-3 shrink-0 rounded-sm ${color}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-slate-800">{label}</span>
                      <span className="block truncate text-xs text-slate-500">{hint}</span>
                    </span>
                    <span className="text-right">
                      <span className="block text-lg font-bold leading-tight">{m.statuses[status] ?? 0}</span>
                      <span className="block text-xs text-slate-500">{Math.round(share(status))}%</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
