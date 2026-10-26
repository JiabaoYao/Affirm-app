import { useState } from "react";
import { Link } from "react-router-dom";

import { useListTransactionsQuery, type TransactionQuery } from "../../api/transactionsApi";
import type { TransactionStatus } from "../../api/types";
import { EmptyState, ErrorState, FilterChips, PageHeader, Pagination, Spinner, StatusBadge, TableCard } from "../../components/ui";
import { date, item, money } from "../../lib/format";

type Filter = "all" | "action" | "financed" | "declined";
const FILTERS: Record<Filter, TransactionStatus[] | undefined> = {
  all: undefined,
  action: ["approved", "in_review"],
  financed: ["authorized", "captured"],
  declined: ["declined", "cancelled", "voided"],
};
const SIZE = 10;

export default function Purchases() {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<TransactionQuery["sort"]>("-created_at");
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useListTransactionsQuery({ status: FILTERS[filter], sort, page, size: SIZE });

  return (
    <div>
      <PageHeader title="Purchases" subtitle="Every checkout you started with Affirm, including declined and cancelled ones." />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <FilterChips<Filter>
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setPage(1);
          }}
          options={[
            { value: "all", label: "All" },
            { value: "action", label: "Needs action" },
            { value: "financed", label: "Financed" },
            { value: "declined", label: "Declined / cancelled" },
          ]}
        />
        <select className="input sm:max-w-[12rem]" value={sort} onChange={(e) => setSort(e.target.value as TransactionQuery["sort"])} aria-label="Sort">
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="-amount">Amount: high to low</option>
          <option value="amount">Amount: low to high</option>
        </select>
      </div>
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState title="No purchases" body="Start one from the store." action={<Link to="/app/shop" className="btn-primary">Shop</Link>} />
      ) : (
        <>
          <TableCard>
            <table className="table-base">
              <thead className="bg-slate-50">
                <tr>
                  <th>Date</th>
                  <th>Item</th>
                  <th className="text-right">Amount</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data!.items.map((t) => (
                  <tr key={t.id}>
                    <td>{date(t.created_at)}</td>
                    <td>
                      <p className="font-medium text-slate-900">{item(t)}</p>
                      <p className="text-xs text-slate-500">{t.merchant_name}</p>
                    </td>
                    <td className="text-right font-medium">{money(t.amount)}</td>
                    <td>
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="text-right">
                      {t.plan_id ? (
                        <Link to={`/app/loans/${t.plan_id}`} className="font-semibold text-brand-700 hover:underline">
                          View loan
                        </Link>
                      ) : (
                        <Link to={`/app/checkout/${t.id}`} className="font-semibold text-brand-700 hover:underline">
                          {t.status === "approved" ? "Choose plan" : "Details"}
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
