import { useState, type FormEvent } from "react";

import type { Installment, PaymentMethod, PaymentMethodIn } from "../api/types";
import { useAddPaymentMethodMutation } from "../api/walletApi";
import { useAppDispatch } from "../app/hooks";
import { toastAdded } from "../features/ui/toastSlice";
import { getFieldErrors } from "../lib/errors";
import { date, money } from "../lib/format";
import { Field, StatusBadge } from "./ui";

export function ScheduleTable({ installments, preview = false }: { installments: Installment[]; preview?: boolean }) {
  return (
    <table className="table-base">
      <thead className="bg-slate-50">
        <tr>
          <th>#</th>
          <th>Due</th>
          <th className="text-right">Payment</th>
          <th className="hidden text-right sm:table-cell">Principal</th>
          <th className="hidden text-right sm:table-cell">Interest</th>
          {!preview && <th className="text-right">Paid</th>}
          {!preview && <th>Status</th>}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {installments.map((i) => (
          <tr key={i.seq} className={i.days_past_due > 0 ? "bg-rose-50/60" : undefined}>
            <td className="text-slate-400">{i.seq}</td>
            <td>{date(i.due_date)}</td>
            <td className="text-right font-medium">{money(i.amount_due)}</td>
            <td className="hidden text-right sm:table-cell">{money(i.principal)}</td>
            <td className="hidden text-right sm:table-cell">{money(i.interest)}</td>
            {!preview && <td className="text-right">{money(i.amount_paid)}</td>}
            {!preview && (
              <td>
                {i.days_past_due > 0 ? (
                  <StatusBadge status="overdue" label={`${i.days_past_due}d overdue`} />
                ) : (
                  <StatusBadge status={i.status} />
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ProgressBar({ paid, total }: { paid: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((paid / total) * 100)) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" aria-label={`${pct}% paid`}>
      <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function methodLabel(m: PaymentMethod | undefined | null): string {
  if (!m) return "No payment method";
  return `${m.label} ••${m.last4}`;
}

export function MethodSelect({
  methods,
  value,
  onChange,
  id,
}: {
  methods: PaymentMethod[];
  value: number | null;
  onChange: (id: number) => void;
  id?: string;
}) {
  return (
    <select id={id} className="input" value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))}>
      {methods.map((m) => (
        <option key={m.id} value={m.id}>
          {methodLabel(m)} {m.is_default ? "(default)" : ""}
        </option>
      ))}
    </select>
  );
}

/** Mock bank/card form: only a nickname and the last 4 digits ever leave the browser. */
export function PaymentMethodForm({ onAdded, compact = false }: { onAdded?: (m: PaymentMethod) => void; compact?: boolean }) {
  const [form, setForm] = useState<PaymentMethodIn>({ kind: "bank", label: "", last4: "", is_default: false });
  const [add, { isLoading, error }] = useAddPaymentMethodMutation();
  const dispatch = useAppDispatch();
  const errors = getFieldErrors(error);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const method = await add(form).unwrap();
      dispatch(toastAdded("success", `${methodLabel(method)} added.`));
      setForm({ kind: form.kind, label: "", last4: "", is_default: false });
      onAdded?.(method);
    } catch {
      // Shown inline (422) or as a toast.
    }
  }

  return (
    <form onSubmit={submit} className={`grid gap-3 ${compact ? "sm:grid-cols-4" : "sm:grid-cols-2"}`}>
      <div>
        <label className="label" htmlFor="pm-kind">
          Type
        </label>
        <select
          id="pm-kind"
          className="input"
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value as PaymentMethodIn["kind"] })}
        >
          <option value="bank">Bank account</option>
          <option value="card">Debit card</option>
        </select>
      </div>
      <Field
        label="Nickname"
        placeholder={form.kind === "bank" ? "Chase Checking" : "Visa Debit"}
        value={form.label}
        onChange={(e) => setForm({ ...form, label: e.target.value })}
        error={errors.label}
        required
        maxLength={60}
      />
      <Field
        label="Last 4 digits"
        placeholder="1234"
        inputMode="numeric"
        value={form.last4}
        onChange={(e) => setForm({ ...form, last4: e.target.value.replace(/\D/g, "").slice(0, 4) })}
        error={errors.last4}
        required
        pattern="\d{4}"
        title="Exactly 4 digits"
      />
      <div className="flex items-end">
        <button className="btn-primary w-full" disabled={isLoading}>
          {isLoading ? "Adding…" : "Add method"}
        </button>
      </div>
    </form>
  );
}
