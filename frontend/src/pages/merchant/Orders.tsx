import { useState } from "react";

import { useListTransactionsQuery, type TransactionQuery } from "../../api/transactionsApi";
import type { TransactionStatus } from "../../api/types";
import { EmptyState, ErrorState, FilterChips, PageHeader, Pagination, Spinner } from "../../components/ui";
import OrdersTable from "./OrdersTable";

type Filter = "all" | "authorized" | "captured" | "closed" | "declined";
const FILTERS: Record<Filter, TransactionStatus[] | undefined> = {
  all: undefined,
  authorized: ["authorized"],
  captured: ["captured"],
  closed: ["voided", "cancelled"],
  declined: ["declined"],
};
const SIZE = 10;

export default function Orders() {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<TransactionQuery["sort"]>("-created_at");
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = useListTransactionsQuery(
    { status: FILTERS[filter], sort, page, size: SIZE },
    { pollingInterval: 15000 },
  );

  return (
    <div>
      <PageHeader title="Orders" subtitle="Affirm checkouts at your store. Capture an order when it ships, or void it if you can't fulfill it." />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <FilterChips<Filter>
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setPage(1);
          }}
          options={[
            { value: "all", label: "All" },
            { value: "authorized", label: "To capture" },
            { value: "captured", label: "Captured" },
            { value: "closed", label: "Voided / cancelled" },
            { value: "declined", label: "Declined" },
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
        <EmptyState title="No orders here" body="Orders appear when shoppers check out with Affirm." />
      ) : (
        <div className={isFetching ? "opacity-70 transition" : "transition"}>
          <OrdersTable orders={data!.items} />
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
