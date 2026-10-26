import { useState, type FormEvent } from "react";

import { useDecideReviewMutation, useReviewsQuery } from "../../api/adminApi";
import type { Transaction } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { EmptyState, ErrorState, Modal, PageHeader, Pagination, Spinner, TableCard } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { dateTime, money } from "../../lib/format";

const SIZE = 10;

function DecisionModal({ tx, approve, onClose }: { tx: Transaction | null; approve: boolean; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [decide, { isLoading }] = useDecideReviewMutation();
  const dispatch = useAppDispatch();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!tx) return;
    try {
      await decide({ id: tx.id, approve, reason }).unwrap();
      dispatch(toastAdded("success", `Application #${tx.id} ${approve ? "approved" : "declined"}. The shopper was notified.`));
      setReason("");
      onClose();
    } catch {
      // toast from the global handler
    }
  }

  return (
    <Modal open={tx !== null} title={approve ? "Approve application" : "Decline application"} onClose={onClose}>
      {tx && (
        <form onSubmit={submit} className="space-y-4 text-sm">
          <p className="text-slate-600">
            {tx.customer_name} ({tx.customer_email}) wants {money(tx.amount)} for {tx.product_name} at {tx.merchant_name}. Score {tx.credit_score}, tier{" "}
            {tx.risk_tier}.
          </p>
          <div>
            <label className="label" htmlFor="review-reason">
              {approve ? "Internal note (optional)" : "Reason shown to the shopper"}
            </label>
            <textarea
              id="review-reason"
              className="input min-h-24"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={255}
              placeholder={approve ? "Verified identity and income." : "We couldn't verify your identity."}
            />
          </div>
          <button className={approve ? "btn-primary w-full" : "btn-danger w-full"} disabled={isLoading}>
            {approve ? "Approve" : "Decline"}
          </button>
        </form>
      )}
    </Modal>
  );
}

export default function Reviews() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useReviewsQuery({ page }, { pollingInterval: 15000 });
  const [deciding, setDeciding] = useState<{ tx: Transaction; approve: boolean } | null>(null);

  return (
    <div>
      <PageHeader title="Manual review" subtitle="Applications the risk rules flagged (score band set to 'review'). Oldest first." />
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState title="Queue is empty" body="New flagged applications show up here automatically." />
      ) : (
        <>
          <TableCard>
            <table className="table-base">
              <thead className="bg-slate-50">
                <tr>
                  <th>Submitted</th>
                  <th>Shopper</th>
                  <th>Purchase</th>
                  <th className="text-right">Amount</th>
                  <th>Score</th>
                  <th className="text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data!.items.map((t) => (
                  <tr key={t.id}>
                    <td>{dateTime(t.created_at)}</td>
                    <td>
                      <p className="font-medium text-slate-900">{t.customer_name}</p>
                      <p className="text-xs text-slate-500">{t.customer_email}</p>
                    </td>
                    <td>
                      {t.product_name}
                      <p className="text-xs text-slate-500">{t.merchant_name}</p>
                    </td>
                    <td className="text-right font-medium">{money(t.amount)}</td>
                    <td>
                      <span className="font-semibold">{t.credit_score}</span> <span className="text-xs text-slate-500">tier {t.risk_tier}</span>
                    </td>
                    <td>
                      <div className="flex justify-end gap-1.5">
                        <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => setDeciding({ tx: t, approve: true })}>
                          Approve
                        </button>
                        <button className="btn-ghost px-3 py-1.5 text-xs text-rose-700" onClick={() => setDeciding({ tx: t, approve: false })}>
                          Decline
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </>
      )}
      <DecisionModal tx={deciding?.tx ?? null} approve={deciding?.approve ?? true} onClose={() => setDeciding(null)} />
    </div>
  );
}
