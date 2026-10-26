import { useState } from "react";

import { useDelinquencyQuery } from "../../api/adminApi";
import type { DelinquencyBucket } from "../../api/types";
import { EmptyState, ErrorState, FilterChips, PageHeader, Spinner, StatCard, TableCard } from "../../components/ui";
import { date, money } from "../../lib/format";

type Filter = DelinquencyBucket | "all";

const BUCKET_STYLE: Record<DelinquencyBucket, string> = {
  "1-30": "bg-amber-100 text-amber-800",
  "31-60": "bg-orange-100 text-orange-800",
  "60+": "bg-rose-100 text-rose-800",
};

export default function Delinquency() {
  const [filter, setFilter] = useState<Filter>("all");
  const all = useDelinquencyQuery({});
  const { data, isLoading, error, refetch } = useDelinquencyQuery({ bucket: filter === "all" ? undefined : filter });
  const counts = (bucket: DelinquencyBucket) => all.data?.filter((l) => l.bucket === bucket) ?? [];
  const sum = (rows: { overdue_amount: string }[]) => rows.reduce((s, r) => s + Number(r.overdue_amount), 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Delinquency" subtitle="Active loans with a missed installment, grouped by days past due. Affirm never charges late fees." />
      <div className="grid gap-4 sm:grid-cols-3">
        {(["1-30", "31-60", "60+"] as DelinquencyBucket[]).map((b) => (
          <StatCard key={b} tone={b === "60+" && counts(b).length ? "danger" : "default"} label={`${b} days`} value={counts(b).length} hint={`${money(sum(counts(b)))} past due`} />
        ))}
      </div>
      <FilterChips<Filter>
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: "All" },
          { value: "1-30", label: "1–30 days" },
          { value: "31-60", label: "31–60 days" },
          { value: "60+", label: "60+ days" },
        ]}
      />
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.length === 0 ? (
        <EmptyState title="No past-due loans" body="Everyone is current in this bucket." />
      ) : (
        <TableCard>
          <table className="table-base">
            <thead className="bg-slate-50">
              <tr>
                <th>Borrower</th>
                <th>Loan</th>
                <th>Bucket</th>
                <th className="text-right">Days late</th>
                <th className="text-right">Past due</th>
                <th className="text-right">Balance</th>
                <th>Oldest due</th>
                <th>Autopay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data!.map((l) => (
                <tr key={l.plan_id}>
                  <td>
                    <p className="font-medium text-slate-900">{l.customer_name}</p>
                    <p className="text-xs text-slate-500">{l.customer_email}</p>
                  </td>
                  <td>
                    #{l.plan_id} · {l.product_name}
                    <p className="text-xs text-slate-500">{l.merchant_name}</p>
                  </td>
                  <td>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${BUCKET_STYLE[l.bucket]}`}>{l.bucket}</span>
                  </td>
                  <td className="text-right font-semibold">{l.days_past_due}</td>
                  <td className="text-right font-medium text-rose-700">{money(l.overdue_amount)}</td>
                  <td className="text-right">{money(l.remaining_balance)}</td>
                  <td>{date(l.next_due_date)}</td>
                  <td>{l.autopay_enabled ? "On" : "Off"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
      )}
    </div>
  );
}
