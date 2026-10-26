import { useEffect, useState } from "react";

import { useRiskTiersQuery, useUpdateRiskTierMutation } from "../../api/adminApi";
import type { RiskTier, TierDecision } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { ErrorState, PageHeader, Spinner, StatusBadge, TableCard } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";

const TERMS = [0, 3, 6, 12, 24];

function TierRow({ tier }: { tier: RiskTier }) {
  const [decision, setDecision] = useState<TierDecision>(tier.decision);
  const [aprPct, setAprPct] = useState(String(Math.round(Number(tier.apr) * 10000) / 100));
  const [maxAmount, setMaxAmount] = useState(tier.max_amount);
  const [maxTerm, setMaxTerm] = useState(tier.max_term_months);
  const [update, { isLoading }] = useUpdateRiskTierMutation();
  const dispatch = useAppDispatch();

  useEffect(() => {
    setDecision(tier.decision);
    setAprPct(String(Math.round(Number(tier.apr) * 10000) / 100));
    setMaxAmount(tier.max_amount);
    setMaxTerm(tier.max_term_months);
  }, [tier]);

  const apr = (Number(aprPct) / 100).toFixed(4);
  const dirty = decision !== tier.decision || apr !== tier.apr || Number(maxAmount) !== Number(tier.max_amount) || maxTerm !== tier.max_term_months;

  async function save() {
    try {
      await update({ id: tier.id, decision, apr, max_amount: Number(maxAmount).toFixed(2), max_term_months: maxTerm }).unwrap();
      dispatch(toastAdded("success", `Tier ${tier.name} updated. New checkouts use the new rules.`));
    } catch {
      // toast from the global handler
    }
  }

  return (
    <tr>
      <td>
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-bold text-white">{tier.name}</span>
      </td>
      <td className="font-medium">
        {tier.min_score}–{tier.max_score}
      </td>
      <td>
        <div className="flex items-center gap-2">
          <select className="input w-32 py-1.5" value={decision} onChange={(e) => setDecision(e.target.value as TierDecision)} aria-label={`Tier ${tier.name} decision`}>
            <option value="approve">Approve</option>
            <option value="review">Review</option>
            <option value="decline">Decline</option>
          </select>
          <StatusBadge status={decision} />
        </div>
      </td>
      <td>
        <div className="flex items-center gap-1">
          <input className="input w-20 py-1.5" type="number" min="0" max="36" step="0.25" value={aprPct} onChange={(e) => setAprPct(e.target.value)} aria-label={`Tier ${tier.name} APR`} />
          <span className="text-slate-500">%</span>
        </div>
      </td>
      <td>
        <div className="flex items-center gap-1">
          <span className="text-slate-500">$</span>
          <input className="input w-28 py-1.5" type="number" min="0" step="100" value={maxAmount} onChange={(e) => setMaxAmount(e.target.value)} aria-label={`Tier ${tier.name} limit`} />
        </div>
      </td>
      <td>
        <select className="input w-24 py-1.5" value={maxTerm} onChange={(e) => setMaxTerm(Number(e.target.value))} aria-label={`Tier ${tier.name} max term`}>
          {TERMS.map((t) => (
            <option key={t} value={t}>
              {t === 0 ? "None" : `${t} mo`}
            </option>
          ))}
        </select>
      </td>
      <td className="text-right">
        <button className="btn-primary px-3 py-1.5 text-xs" disabled={!dirty || isLoading} onClick={save}>
          Save
        </button>
      </td>
    </tr>
  );
}

export default function RiskTiers() {
  const { data, isLoading, error, refetch } = useRiskTiersQuery();
  return (
    <div className="space-y-4">
      <PageHeader
        title="Risk tiers"
        subtitle="Underwriting rules by credit score band: whether to approve, the APR for non-promo plans, the spending limit and the longest term. Changes apply to new checkouts. Signed loans keep their terms."
      />
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : (
        <TableCard>
          <table className="table-base">
            <thead className="bg-slate-50">
              <tr>
                <th>Tier</th>
                <th>Score band</th>
                <th>Decision</th>
                <th>APR</th>
                <th>Spending limit</th>
                <th>Max term</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data!.map((t) => (
                <TierRow key={t.id} tier={t} />
              ))}
            </tbody>
          </table>
        </TableCard>
      )}
      <p className="text-xs text-slate-500">Merchant-funded 0% APR programs stay at 0% for every approved tier.</p>
    </div>
  );
}
