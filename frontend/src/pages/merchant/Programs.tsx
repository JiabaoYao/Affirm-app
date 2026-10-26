import { useState, type FormEvent } from "react";

import { useCreateProgramMutation, useMerchantSummaryQuery, useProgramsQuery, useUpdateProgramMutation } from "../../api/merchantApi";
import type { Program } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { EmptyState, ErrorState, Field, Modal, PageHeader, Spinner } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { getFieldErrors } from "../../lib/errors";
import { money, percent } from "../../lib/format";

const TERMS = [3, 6, 12, 24];

function ProgramForm({ program, takenTerms, onDone }: { program?: Program; takenTerms: number[]; onDone: () => void }) {
  const freeTerms = TERMS.filter((t) => !takenTerms.includes(t));
  const [term, setTerm] = useState(program?.term_months ?? freeTerms[0]);
  const [promo, setPromo] = useState(program?.zero_apr_promo ?? false);
  const [min, setMin] = useState(program?.min_amount ?? "50.00");
  const [max, setMax] = useState(program?.max_amount ?? "30000.00");
  const [create, createState] = useCreateProgramMutation();
  const [update, updateState] = useUpdateProgramMutation();
  const state = program ? updateState : createState;
  const errors = getFieldErrors(state.error);
  const dispatch = useAppDispatch();

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (program) await update({ id: program.id, zero_apr_promo: promo, min_amount: min, max_amount: max }).unwrap();
      else await create({ term_months: term, zero_apr_promo: promo, min_amount: min, max_amount: max }).unwrap();
      dispatch(toastAdded("success", program ? "Program updated for new checkouts." : `${term}-month plans are now offered at checkout.`));
      onDone();
    } catch {
      // inline (422) or toast
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {!program && (
        <div>
          <label className="label" htmlFor="program-term">
            Term
          </label>
          <select id="program-term" className="input" value={term} onChange={(e) => setTerm(Number(e.target.value))}>
            {freeTerms.map((t) => (
              <option key={t} value={t}>
                {t} months
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Min order" value={min} onChange={(e) => setMin(e.target.value)} error={errors.min_amount} inputMode="decimal" required />
        <Field label="Max order" value={max} onChange={(e) => setMax(e.target.value)} error={errors.max_amount ?? errors[""]} inputMode="decimal" required />
      </div>
      <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-3 text-sm">
        <input type="checkbox" className="mt-0.5 h-4 w-4 rounded text-brand-600" checked={promo} onChange={(e) => setPromo(e.target.checked)} />
        <span>
          <strong>0% APR promo (merchant-funded)</strong>
          <span className="block text-slate-500">Shoppers pay no interest on this term, and you pay the extra promo fee on these orders.</span>
        </span>
      </label>
      <button className="btn-primary w-full" disabled={state.isLoading || (!program && freeTerms.length === 0)}>
        {program ? "Save changes" : "Offer this term"}
      </button>
    </form>
  );
}

export default function Programs() {
  const { data: programs = [], isLoading, error, refetch } = useProgramsQuery();
  const { data: summary } = useMerchantSummaryQuery();
  const [update, { isLoading: toggling }] = useUpdateProgramMutation();
  const [editing, setEditing] = useState<Program | "new" | null>(null);
  const dispatch = useAppDispatch();
  const taken = programs.map((p) => p.term_months);

  return (
    <div>
      <PageHeader
        title="Financing programs"
        subtitle={
          <>
            Choose which plans shoppers can see at your checkout. Affirm decides each shopper's APR and approval. You decide the terms and promos.
            {summary && ` Your fee: ${percent(summary.fee_rate)}, or ${percent(Number(summary.fee_rate) + Number(summary.promo_fee_rate))} on 0% promos.`}
          </>
        }
        actions={
          <button className="btn-primary" onClick={() => setEditing("new")} disabled={taken.length >= TERMS.length}>
            Add a term
          </button>
        }
      />
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : programs.length === 0 ? (
        <EmptyState
          title="No programs yet"
          body="Add at least one term so shoppers can pay over time at your store."
          action={<button className="btn-primary" onClick={() => setEditing("new")}>Add a term</button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {programs.map((p) => (
            <div key={p.id} className={`card p-5 ${p.active ? "" : "opacity-60"}`}>
              <div className="flex items-start justify-between">
                <p className="text-3xl font-bold">
                  {p.term_months}
                  <span className="text-base font-medium text-slate-500"> mo</span>
                </p>
                {p.zero_apr_promo ? (
                  <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">0% APR</span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">Risk-based APR</span>
                )}
              </div>
              <p className="mt-3 text-sm text-slate-600">
                Orders {money(p.min_amount)} – {money(p.max_amount)}
              </p>
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded text-brand-600"
                    checked={p.active}
                    disabled={toggling}
                    onChange={async (e) => {
                      try {
                        await update({ id: p.id, active: e.target.checked }).unwrap();
                        dispatch(toastAdded("success", `${p.term_months}-month plan ${e.target.checked ? "enabled" : "paused"}.`));
                      } catch {
                        // toast from the global handler
                      }
                    }}
                  />
                  {p.active ? "Offered" : "Paused"}
                </label>
                <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setEditing(p)}>
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <Modal
        open={editing !== null}
        title={editing === "new" ? "Offer a new term" : editing ? `Edit ${editing.term_months}-month program` : ""}
        onClose={() => setEditing(null)}
      >
        {editing !== null && <ProgramForm program={editing === "new" ? undefined : editing} takenTerms={taken} onDone={() => setEditing(null)} />}
      </Modal>
    </div>
  );
}
