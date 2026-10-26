import { useEffect, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { getErrorMessage } from "../lib/errors";
import { titleCase } from "../lib/format";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-500" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      {label}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 7h16M4 12h16M4 17h10" strokeLinecap="round" />
        </svg>
      </div>
      <h3 className="font-semibold text-slate-900">{title}</h3>
      {body && <p className="mt-1 max-w-md text-sm text-slate-500">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="card border-rose-200 bg-rose-50 px-6 py-8 text-center" role="alert">
      <p className="font-semibold text-rose-800">Couldn't load this</p>
      <p className="mt-1 text-sm text-rose-700">{getErrorMessage(error)}</p>
      {onRetry && (
        <button className="btn-secondary mt-4" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "error" | "success" | "warning"; children: ReactNode }) {
  const styles = {
    info: "border-brand-200 bg-brand-50 text-brand-900",
    error: "border-rose-200 bg-rose-50 text-rose-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[kind];
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${styles}`} role={kind === "error" ? "alert" : undefined}>
      {children}
    </div>
  );
}

const BADGE_COLORS: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-800",
  active: "bg-emerald-100 text-emerald-800",
  captured: "bg-emerald-100 text-emerald-800",
  paid: "bg-emerald-100 text-emerald-800",
  paid_off: "bg-slate-200 text-slate-700",
  authorized: "bg-sky-100 text-sky-800",
  pending_capture: "bg-sky-100 text-sky-800",
  pending: "bg-amber-100 text-amber-800",
  partial: "bg-amber-100 text-amber-800",
  in_review: "bg-amber-100 text-amber-800",
  review: "bg-amber-100 text-amber-800",
  approve: "bg-emerald-100 text-emerald-800",
  declined: "bg-rose-100 text-rose-800",
  decline: "bg-rose-100 text-rose-800",
  overdue: "bg-rose-100 text-rose-800",
  suspended: "bg-rose-100 text-rose-800",
  voided: "bg-slate-200 text-slate-600",
  cancelled: "bg-slate-200 text-slate-600",
};

const BADGE_LABELS: Record<string, string> = {
  pending_capture: "Awaiting shipment",
  authorized: "Awaiting capture",
  in_review: "In review",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE_COLORS[status] ?? "bg-slate-100 text-slate-700"}`}
    >
      {label ?? BADGE_LABELS[status] ?? titleCase(status)}
    </span>
  );
}

export function StatCard({ label, value, hint, tone = "default" }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "default" | "brand" | "danger" }) {
  const toneClass = tone === "brand" ? "bg-brand-600 text-white border-brand-600" : tone === "danger" ? "border-rose-200 bg-rose-50" : "";
  return (
    <div className={`card p-5 ${toneClass}`}>
      <p className={`text-xs font-semibold uppercase tracking-wide ${tone === "brand" ? "text-brand-100" : "text-slate-500"}`}>{label}</p>
      <p className="mt-2 text-2xl font-bold tracking-tight">{value}</p>
      {hint && <p className={`mt-1 text-xs ${tone === "brand" ? "text-brand-100" : "text-slate-500"}`}>{hint}</p>}
    </div>
  );
}

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Field({ label, error, hint, id, className, ...props }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={className}>
      <label htmlFor={inputId} className="label">
        {label}
      </label>
      <input
        id={inputId}
        className={`input ${error ? "border-rose-400 focus:border-rose-500 focus:ring-rose-100" : ""}`}
        aria-invalid={Boolean(error)}
        aria-describedby={error || hint ? `${inputId}-msg` : undefined}
        {...props}
      />
      {(error || hint) && (
        <p id={`${inputId}-msg`} className={`mt-1 text-xs ${error ? "text-rose-600" : "text-slate-500"}`}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}

export function Pagination({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (total <= size) return null;
  return (
    <div className="flex items-center justify-between gap-3 px-1 pt-4 text-sm text-slate-600">
      <span>
        {(page - 1) * size + 1}–{Math.min(page * size, total)} of {total}
      </span>
      <div className="flex gap-2">
        <button className="btn-secondary px-3 py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button className="btn-secondary px-3 py-1.5" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

export function FilterChips<T extends string>({ options, value, onChange }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
            o.value === value ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  // Portal to <body>: a modal opened from a table cell must not inherit its nowrap/alignment styles.
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="card w-full max-w-md whitespace-normal p-6 text-left"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="btn-ghost -m-2 px-2" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <div className="text-sm text-slate-600">{body}</div>
      <div className="mt-6 flex justify-end gap-2">
        <button className="btn-secondary" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} disabled={busy}>
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function TableCard({ children }: { children: ReactNode }) {
  return <div className="card overflow-x-auto">{children}</div>;
}
