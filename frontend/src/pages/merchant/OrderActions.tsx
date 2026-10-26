import { useState, type FormEvent } from "react";

import { useCaptureOrderMutation, useUpdateTrackingMutation, useVoidOrderMutation } from "../../api/transactionsApi";
import type { Transaction } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { ConfirmDialog, Modal } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { item, money } from "../../lib/format";

/** Capture (ship), void, and tracking for one order. Only authorized/captured orders have actions. */
export default function OrderActions({ order }: { order: Transaction }) {
  const [capture, { isLoading: capturing }] = useCaptureOrderMutation();
  const [voidOrder, { isLoading: voiding }] = useVoidOrderMutation();
  const [track, { isLoading: tracking }] = useUpdateTrackingMutation();
  const [dialog, setDialog] = useState<"capture" | "void" | "tracking" | null>(null);
  const [trackingNumber, setTrackingNumber] = useState(order.tracking_number ?? "");
  const dispatch = useAppDispatch();

  async function run(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      dispatch(toastAdded("success", message));
    } catch {
      // toast from the global handler
    }
    setDialog(null);
  }

  async function saveTracking(e: FormEvent) {
    e.preventDefault();
    await run(() => track({ id: order.id, tracking_number: trackingNumber }).unwrap(), "Tracking number saved.");
  }

  if (order.status !== "authorized" && order.status !== "captured") return <span className="text-xs text-slate-400">—</span>;

  const net = Number(order.amount) - Number(order.merchant_fee ?? 0);
  return (
    <div className="flex justify-end gap-1.5">
      {order.status === "authorized" && (
        <>
          <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => setDialog("capture")}>
            Capture
          </button>
          <button className="btn-ghost px-3 py-1.5 text-xs text-rose-700" onClick={() => setDialog("void")}>
            Void
          </button>
        </>
      )}
      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setDialog("tracking")}>
        {order.tracking_number ? "Tracking" : "Add tracking"}
      </button>

      <ConfirmDialog
        open={dialog === "capture"}
        title="Capture this order?"
        body={
          <>
            Capture when <strong>{item(order)}</strong> ships. The shopper's loan becomes active and Affirm pays you{" "}
            <strong>{money(net)}</strong> ({money(order.amount)} minus a {money(order.merchant_fee)} fee).
          </>
        }
        confirmLabel="Capture & get paid"
        busy={capturing}
        onClose={() => setDialog(null)}
        onConfirm={() => run(() => capture(order.id).unwrap(), `Captured. ${money(net)} is on its way to you.`)}
      />
      <ConfirmDialog
        open={dialog === "void"}
        title="Void this order?"
        body="Use this if you can't fulfill the order. The shopper's loan is cancelled, they owe nothing, and you won't be paid."
        confirmLabel="Void order"
        danger
        busy={voiding}
        onClose={() => setDialog(null)}
        onConfirm={() => run(() => voidOrder(order.id).unwrap(), "Order voided. The shopper's loan was cancelled.")}
      />
      <Modal open={dialog === "tracking"} title="Shipment tracking" onClose={() => setDialog(null)}>
        <form onSubmit={saveTracking} className="space-y-4">
          <input className="input" value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} placeholder="1Z999AA10123456784" required maxLength={100} />
          <button className="btn-primary w-full" disabled={tracking}>
            Save tracking number
          </button>
        </form>
      </Modal>
    </div>
  );
}
