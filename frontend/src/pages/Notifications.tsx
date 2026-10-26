import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useMarkAllReadMutation, useMarkReadMutation, useNotificationsQuery } from "../api/notificationsApi";
import { EmptyState, ErrorState, FilterChips, PageHeader, Pagination, Spinner } from "../components/ui";
import { timeAgo } from "../lib/format";

const SIZE = 15;

export default function Notifications() {
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useNotificationsQuery({ page, size: SIZE, unread_only: filter === "unread" });
  const [markRead] = useMarkReadMutation();
  const [markAll, { isLoading: markingAll }] = useMarkAllReadMutation();
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="Notifications"
        subtitle="Approvals, shipments, payments and reminders."
        actions={
          <button className="btn-secondary" onClick={() => markAll()} disabled={markingAll || !data?.unread}>
            Mark all as read
          </button>
        }
      />
      <div className="mb-4">
        <FilterChips
          value={filter}
          onChange={(f) => {
            setFilter(f);
            setPage(1);
          }}
          options={[
            { value: "all", label: "All" },
            { value: "unread", label: `Unread${data ? ` (${data.unread})` : ""}` },
          ]}
        />
      </div>
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState title={filter === "unread" ? "You're all caught up" : "No notifications yet"} />
      ) : (
        <>
          <ul className="card divide-y divide-slate-100">
            {data!.items.map((n) => (
              <li key={n.id}>
                <button
                  className={`flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-slate-50 ${n.read_at ? "" : "bg-brand-50/50"}`}
                  onClick={() => {
                    if (!n.read_at) void markRead(n.id);
                    if (n.link) navigate(n.link);
                  }}
                >
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-brand-600"}`} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="font-semibold text-slate-900">{n.title}</span>
                      <span className="shrink-0 text-xs text-slate-400">{timeAgo(n.created_at)}</span>
                    </span>
                    <span className="mt-0.5 block text-sm text-slate-600">{n.body}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
