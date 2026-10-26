import { useState } from "react";

import type { PaymentMethod } from "../../api/types";
import { useMakeDefaultMethodMutation, usePaymentMethodsQuery, useRemovePaymentMethodMutation } from "../../api/walletApi";
import { useAppDispatch } from "../../app/hooks";
import { methodLabel, PaymentMethodForm } from "../../components/loan";
import { ConfirmDialog, EmptyState, ErrorState, PageHeader, Spinner } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";

export default function Wallet() {
  const { data: methods = [], isLoading, error, refetch } = usePaymentMethodsQuery();
  const [makeDefault] = useMakeDefaultMethodMutation();
  const [remove, { isLoading: removing }] = useRemovePaymentMethodMutation();
  const [toRemove, setToRemove] = useState<PaymentMethod | null>(null);
  const dispatch = useAppDispatch();

  return (
    <div className="space-y-6">
      <PageHeader title="Wallet" subtitle="Bank accounts and debit cards for autopay and one-time payments." />
      <div className="card p-5">
        <h2 className="mb-4 font-semibold">Add a payment method</h2>
        <PaymentMethodForm />
        <p className="mt-3 text-xs text-slate-500">Demo only: we store a nickname and the last 4 digits, never a full account or card number.</p>
      </div>

      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : methods.length === 0 ? (
        <EmptyState title="No payment methods yet" body="Add one above to turn on autopay." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {methods.map((m) => (
            <div key={m.id} className="card flex items-center justify-between gap-3 p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-lg">{m.kind === "bank" ? "🏦" : "💳"}</span>
                <div>
                  <p className="font-semibold">{methodLabel(m)}</p>
                  <p className="text-xs text-slate-500">{m.kind === "bank" ? "Bank account" : "Debit card"}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {m.is_default ? (
                  <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700">Default</span>
                ) : (
                  <button
                    className="btn-ghost px-3 py-1.5"
                    onClick={async () => {
                      await makeDefault(m.id).unwrap().catch(() => undefined);
                    }}
                  >
                    Make default
                  </button>
                )}
                <button className="btn-ghost px-3 py-1.5 text-rose-700" onClick={() => setToRemove(m)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={toRemove !== null}
        title="Remove payment method?"
        body={
          <>
            <strong>{methodLabel(toRemove)}</strong> will be removed. Plans that autopay from it switch to your default method, or autopay turns off if you
            have none.
          </>
        }
        confirmLabel="Remove"
        danger
        busy={removing}
        onClose={() => setToRemove(null)}
        onConfirm={async () => {
          try {
            await remove(toRemove!.id).unwrap();
            dispatch(toastAdded("success", "Payment method removed."));
          } catch {
            // toast from the global handler
          }
          setToRemove(null);
        }}
      />
    </div>
  );
}
