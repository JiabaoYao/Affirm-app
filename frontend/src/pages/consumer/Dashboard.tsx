import { Link } from "react-router-dom";

import { useListPlansQuery } from "../../api/plansApi";
import { useListTransactionsQuery } from "../../api/transactionsApi";
import { useAppSelector } from "../../app/hooks";
import { Alert, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from "../../components/ui";
import { selectUser } from "../../features/auth/authSlice";
import { date, money } from "../../lib/format";
import CreditCard from "./CreditCard";
import PlanCard from "./PlanCard";

export default function ConsumerDashboard() {
  const user = useAppSelector(selectUser);
  const plans = useListPlansQuery({ status: ["active", "pending_capture"], size: 50 });
  const pending = useListTransactionsQuery({ status: ["approved", "in_review"], size: 5 });

  const live = plans.data?.items ?? [];
  const active = live.filter((p) => p.status === "active");
  const overdue = active.filter((p) => p.days_past_due > 0);
  const next = [...active].filter((p) => p.next_due_date).sort((a, b) => a.next_due_date!.localeCompare(b.next_due_date!))[0];
  const owed = live.reduce((sum, p) => sum + Number(p.remaining_balance), 0);

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Hi, ${user?.full_name.split(" ")[0] || "there"}`}
        subtitle="Your loans, upcoming payments and spending power in one place."
        actions={
          <Link to="/app/shop" className="btn-primary">
            Shop with Affirm
          </Link>
        }
      />

      {overdue.length > 0 && (
        <Alert kind="error">
          <strong>You have {overdue.length === 1 ? "a payment" : `${overdue.length} loans with payments`} past due.</strong>{" "}
          {overdue.map((p) => (
            <Link key={p.id} to={`/app/loans/${p.id}`} className="ml-1 font-semibold underline">
              Pay {money(p.overdue_amount)} for {p.product_name}
            </Link>
          ))}
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CreditCard />
        </div>
        <div className="grid gap-4">
          <StatCard
            label="Next payment"
            value={next ? money(next.monthly_payment) : "—"}
            hint={next ? `${date(next.next_due_date)} · ${next.product_name}` : "No payments due"}
          />
          <StatCard label="Total balance" value={money(owed)} hint={`${live.length} open loan${live.length === 1 ? "" : "s"}`} />
        </div>
      </div>

      {(pending.data?.items.length ?? 0) > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Finish checking out</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {pending.data!.items.map((t) => (
              <Link key={t.id} to={`/app/checkout/${t.id}`} className="card flex items-center justify-between gap-3 p-4 hover:border-brand-300">
                <div>
                  <p className="font-semibold">{t.product_name}</p>
                  <p className="text-sm text-slate-500">
                    {t.merchant_name} · {money(t.amount)}
                  </p>
                </div>
                <span className="text-sm font-semibold text-brand-700">
                  {t.status === "approved" ? "Choose a plan →" : "In review…"}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Open loans</h2>
          <Link to="/app/loans" className="text-sm font-semibold text-brand-700 hover:underline">
            All loans
          </Link>
        </div>
        {plans.isLoading ? (
          <Spinner />
        ) : plans.error ? (
          <ErrorState error={plans.error} onRetry={plans.refetch} />
        ) : live.length === 0 ? (
          <EmptyState
            title="No open loans"
            body="When you buy something with Affirm, your payment plan shows up here."
            action={
              <Link to="/app/shop" className="btn-primary">
                Browse the store
              </Link>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {live.map((p) => (
              <PlanCard key={p.id} plan={p} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
