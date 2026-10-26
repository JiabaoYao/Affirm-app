import { useState, type FormEvent } from "react";

import { useAuditLogQuery, useRunDailyMutation } from "../../api/adminApi";
import type { RunDailyOut } from "../../api/types";
import { Alert, EmptyState, ErrorState, PageHeader, Pagination, Spinner, TableCard } from "../../components/ui";
import { date, dateTime, money } from "../../lib/format";

const SIZE = 15;

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function Operations() {
  const [asOf, setAsOf] = useState(todayIso());
  const [result, setResult] = useState<RunDailyOut | null>(null);
  const [run, { isLoading: running }] = useRunDailyMutation();
  const [page, setPage] = useState(1);
  const audit = useAuditLogQuery({ page, size: SIZE });

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setResult(await run({ as_of: asOf }).unwrap());
    } catch {
      // toast from the global handler
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Operations" subtitle="Run the daily servicing job and audit who changed what." />

      <section className="card p-5">
        <h2 className="font-semibold">Daily servicing job</h2>
        <p className="mt-1 text-sm text-slate-500">
          Normally a scheduler runs this every morning. It charges autopay for installments due by the business date and sends due-soon and overdue
          notifications. Pick a future date to simulate time passing.
        </p>
        <form onSubmit={submit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div>
            <label className="label" htmlFor="as-of">
              Business date
            </label>
            <input id="as-of" type="date" className="input" value={asOf} onChange={(e) => setAsOf(e.target.value)} required />
          </div>
          <button className="btn-primary" disabled={running}>
            {running ? "Running…" : "Run job"}
          </button>
        </form>
        {result && (
          <div className="mt-4">
            <Alert kind="success">
              Ran for {date(result.as_of)}: {result.autopay_payments} autopay payment(s) totaling {money(result.autopay_amount)}, {result.reminders} reminder(s),{" "}
              {result.overdue_notices} overdue notice(s).
            </Alert>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Audit log</h2>
        {audit.isLoading ? (
          <Spinner />
        ) : audit.error ? (
          <ErrorState error={audit.error} onRetry={audit.refetch} />
        ) : audit.data!.items.length === 0 ? (
          <EmptyState title="No changes recorded yet" />
        ) : (
          <>
            <TableCard>
              <table className="table-base">
                <thead className="bg-slate-50">
                  <tr>
                    <th>When</th>
                    <th>Who</th>
                    <th>Action</th>
                    <th>Target</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {audit.data!.items.map((a) => (
                    <tr key={a.id}>
                      <td>{dateTime(a.created_at)}</td>
                      <td>{a.actor_email}</td>
                      <td>
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{a.action}</code>
                      </td>
                      <td>
                        {a.entity} #{a.entity_id}
                      </td>
                      <td className="max-w-xs truncate text-xs text-slate-500" title={JSON.stringify(a.details)}>
                        {Object.entries(a.details)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableCard>
            <Pagination page={page} size={SIZE} total={audit.data!.total} onPage={setPage} />
          </>
        )}
      </section>
    </div>
  );
}
