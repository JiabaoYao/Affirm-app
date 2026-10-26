import { useState, type FormEvent } from "react";

import { useAdminMerchantsQuery, useApproveMerchantMutation, useSuspendMerchantMutation } from "../../api/adminApi";
import type { AdminMerchant, MerchantStatus } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { ConfirmDialog, EmptyState, ErrorState, FilterChips, Modal, PageHeader, Pagination, Spinner, StatusBadge, TableCard } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { date, percent } from "../../lib/format";

type Filter = MerchantStatus | "all";

function ApproveModal({ merchant, onClose }: { merchant: AdminMerchant | null; onClose: () => void }) {
  const [feePct, setFeePct] = useState("3");
  const [promoPct, setPromoPct] = useState("3");
  const [approve, { isLoading }] = useApproveMerchantMutation();
  const dispatch = useAppDispatch();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!merchant) return;
    try {
      await approve({
        id: merchant.user_id,
        fee_rate: (Number(feePct) / 100).toFixed(4),
        promo_fee_rate: (Number(promoPct) / 100).toFixed(4),
      }).unwrap();
      dispatch(toastAdded("success", `${merchant.business_name} is approved and can now sell with Affirm.`));
      onClose();
    } catch {
      // toast from the global handler
    }
  }

  return (
    <Modal open={merchant !== null} title={`Approve ${merchant?.business_name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4 text-sm">
        <p className="text-slate-600">
          Owner: {merchant?.full_name} ({merchant?.email}). Applied {date(merchant?.created_at)}.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="fee">
              Merchant fee (%)
            </label>
            <input id="fee" className="input" type="number" min="0" max="15" step="0.1" value={feePct} onChange={(e) => setFeePct(e.target.value)} required />
          </div>
          <div>
            <label className="label" htmlFor="promo-fee">
              Extra for 0% promos (%)
            </label>
            <input id="promo-fee" className="input" type="number" min="0" max="15" step="0.1" value={promoPct} onChange={(e) => setPromoPct(e.target.value)} required />
          </div>
        </div>
        <button className="btn-primary w-full" disabled={isLoading}>
          Approve merchant
        </button>
      </form>
    </Modal>
  );
}

export default function Merchants() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useAdminMerchantsQuery({ status: filter === "all" ? undefined : filter, page });
  const [suspend, { isLoading: suspending }] = useSuspendMerchantMutation();
  const [approving, setApproving] = useState<AdminMerchant | null>(null);
  const [suspending_, setSuspending] = useState<AdminMerchant | null>(null);
  const dispatch = useAppDispatch();

  return (
    <div>
      <PageHeader title="Merchants" subtitle="Approve new merchant applications, set fee rates, and suspend risky merchants." />
      <div className="mb-5">
        <FilterChips<Filter>
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setPage(1);
          }}
          options={[
            { value: "pending", label: "Pending" },
            { value: "active", label: "Active" },
            { value: "suspended", label: "Suspended" },
            { value: "all", label: "All" },
          ]}
        />
      </div>
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState title={filter === "pending" ? "No applications waiting" : "No merchants here"} />
      ) : (
        <>
          <TableCard>
            <table className="table-base">
              <thead className="bg-slate-50">
                <tr>
                  <th>Business</th>
                  <th>Owner</th>
                  <th>Status</th>
                  <th>Fees</th>
                  <th>Applied</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data!.items.map((m) => (
                  <tr key={m.user_id}>
                    <td className="font-medium text-slate-900">{m.business_name}</td>
                    <td>
                      {m.full_name}
                      <p className="text-xs text-slate-500">{m.email}</p>
                    </td>
                    <td>
                      <StatusBadge status={m.status} />
                    </td>
                    <td>
                      {percent(m.fee_rate)} <span className="text-xs text-slate-500">+{percent(m.promo_fee_rate)} promo</span>
                    </td>
                    <td>{date(m.created_at)}</td>
                    <td>
                      <div className="flex justify-end gap-1.5">
                        {m.status !== "active" && (
                          <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => setApproving(m)}>
                            {m.status === "pending" ? "Approve" : "Reinstate"}
                          </button>
                        )}
                        {m.status !== "suspended" && (
                          <button className="btn-ghost px-3 py-1.5 text-xs text-rose-700" onClick={() => setSuspending(m)}>
                            Suspend
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
          <Pagination page={page} size={data!.size} total={data!.total} onPage={setPage} />
        </>
      )}
      <ApproveModal merchant={approving} onClose={() => setApproving(null)} />
      <ConfirmDialog
        open={suspending_ !== null}
        title={`Suspend ${suspending_?.business_name}?`}
        body="Their products disappear from the store and new Affirm checkouts are blocked. Existing loans are not affected."
        confirmLabel="Suspend"
        danger
        busy={suspending}
        onClose={() => setSuspending(null)}
        onConfirm={async () => {
          try {
            await suspend(suspending_!.user_id).unwrap();
            dispatch(toastAdded("success", `${suspending_!.business_name} suspended.`));
          } catch {
            // toast from the global handler
          }
          setSuspending(null);
        }}
      />
    </div>
  );
}
