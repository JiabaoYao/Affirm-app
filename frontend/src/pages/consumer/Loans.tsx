import { useState } from "react";
import { Link } from "react-router-dom";

import { useListPlansQuery } from "../../api/plansApi";
import type { PlanStatus } from "../../api/types";
import { EmptyState, ErrorState, FilterChips, PageHeader, Pagination, Spinner } from "../../components/ui";
import PlanCard from "./PlanCard";

type Filter = "open" | "paid_off" | "voided" | "all";
const FILTERS: Record<Filter, PlanStatus[] | undefined> = {
  open: ["active", "pending_capture"],
  paid_off: ["paid_off"],
  voided: ["voided"],
  all: undefined,
};
const SIZE = 9;

export default function Loans() {
  const [filter, setFilter] = useState<Filter>("open");
  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error, refetch } = useListPlansQuery({ status: FILTERS[filter], page, size: SIZE });

  return (
    <div>
      <PageHeader title="My loans" subtitle="Every Affirm plan you've signed, with balances and schedules." />
      <div className="mb-5">
        <FilterChips<Filter>
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setPage(1);
          }}
          options={[
            { value: "open", label: "Open" },
            { value: "paid_off", label: "Paid off" },
            { value: "voided", label: "Cancelled" },
            { value: "all", label: "All" },
          ]}
        />
      </div>
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState
          title={filter === "open" ? "No open loans" : "Nothing here yet"}
          body="Loans appear here after you accept a plan at checkout."
          action={
            <Link to="/app/shop" className="btn-primary">
              Shop with Affirm
            </Link>
          }
        />
      ) : (
        <div className={isFetching ? "opacity-60 transition" : "transition"}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data!.items.map((p) => (
              <PlanCard key={p.id} plan={p} />
            ))}
          </div>
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
