import { Link } from "react-router-dom";

import { useMerchantSummaryQuery, useProgramsQuery } from "../../api/merchantApi";
import { useListTransactionsQuery } from "../../api/transactionsApi";
import { Alert, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from "../../components/ui";
import { money, percent } from "../../lib/format";
import OrdersTable from "./OrdersTable";

export default function MerchantDashboard() {
  const summary = useMerchantSummaryQuery();
  const programs = useProgramsQuery();
  const toCapture = useListTransactionsQuery({ status: ["authorized"], size: 5 }, { pollingInterval: 15000 });

  if (summary.isLoading) return <Spinner />;
  if (summary.error || !summary.data) return <ErrorState error={summary.error} onRetry={summary.refetch} />;
  const s = summary.data;
  const activePrograms = programs.data?.filter((p) => p.active) ?? [];
  const decided = s.counts.approved + s.counts.authorized + s.counts.captured + s.counts.voided + s.counts.cancelled + s.counts.declined;

  return (
    <div className="space-y-8">
      <PageHeader
        title={s.business_name}
        subtitle={`Affirm pays you upfront when you capture an order. Your fee: ${percent(s.fee_rate)} (+${percent(s.promo_fee_rate)} on 0% APR promos).`}
        actions={
          <Link to="/merchant/orders" className="btn-primary">
            View all orders
          </Link>
        }
      />
      {programs.data && activePrograms.length === 0 && (
        <Alert kind="warning">
          You don't offer any financing programs yet, so shoppers can't check out with Affirm.{" "}
          <Link to="/merchant/programs" className="font-semibold underline">
            Set up programs
          </Link>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard tone="brand" label="Net payouts" value={money(s.net_payout)} hint={`${money(s.gross_volume)} sales − ${money(s.fees)} fees`} />
        <StatCard label="Awaiting capture" value={money(s.awaiting_capture_amount)} hint={`${s.counts.authorized} order(s) to ship`} />
        <StatCard label="Captured orders" value={s.counts.captured} hint={`${s.counts.voided} voided`} />
        <StatCard label="Approval rate" value={decided ? percent((decided - s.counts.declined) / decided) : "—"} hint={`${s.counts.declined} declined by Affirm`} />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Ready to ship</h2>
        {toCapture.isLoading ? (
          <Spinner />
        ) : toCapture.data?.items.length ? (
          <OrdersTable orders={toCapture.data.items} />
        ) : (
          <EmptyState title="Nothing to capture" body="Orders appear here as soon as a shopper accepts an Affirm plan." />
        )}
      </section>
    </div>
  );
}
