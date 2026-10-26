import { useEffect } from "react";

import { useAppDispatch, useAppSelector } from "../app/hooks";
import { toastDismissed, type Toast } from "../features/ui/toastSlice";

function ToastItem({ toast }: { toast: Toast }) {
  const dispatch = useAppDispatch();
  useEffect(() => {
    const t = setTimeout(() => dispatch(toastDismissed(toast.id)), toast.kind === "error" ? 7000 : 4000);
    return () => clearTimeout(t);
  }, [dispatch, toast]);

  const styles = {
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-rose-200 bg-rose-50 text-rose-900",
    info: "border-slate-200 bg-white text-slate-900",
  }[toast.kind];
  return (
    <div className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${styles}`} role="status">
      <span className="flex-1">{toast.message}</span>
      <button className="text-slate-400 hover:text-slate-700" onClick={() => dispatch(toastDismissed(toast.id))} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}

export default function Toasts() {
  const toasts = useAppSelector((s) => s.toasts);
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 mx-auto flex max-w-md flex-col gap-2 px-4">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
