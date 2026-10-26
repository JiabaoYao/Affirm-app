const PASSWORD = "Password123!";

const ACCOUNTS = [
  { group: "Shoppers", email: "alice@demo.com", note: "Score 780 · has loans" },
  { group: "Shoppers", email: "bob@demo.com", note: "Score 665 · tier C" },
  { group: "Shoppers", email: "carol@demo.com", note: "Score 615 · manual review" },
  { group: "Shoppers", email: "dave@demo.com", note: "Score 560 · declined" },
  { group: "Merchants", email: "shop@demo.com", note: "Demo Electronics" },
  { group: "Merchants", email: "home@demo.com", note: "Cozy Home" },
  { group: "Merchants", email: "newshop@demo.com", note: "Pending approval" },
  { group: "Affirm ops", email: "admin@demo.com", note: "Internal admin" },
];

/** One-click sign-in with the seeded accounts, so a demo never waits on typing. */
export default function DemoAccounts({ onPick, disabled }: { onPick: (email: string, password: string) => void; disabled?: boolean }) {
  const groups = [...new Set(ACCOUNTS.map((a) => a.group))];
  return (
    <details className="rounded-xl border border-dashed border-slate-300 p-3 text-sm" open>
      <summary className="cursor-pointer font-semibold text-slate-700">Demo accounts (password {PASSWORD})</summary>
      <div className="mt-3 space-y-3">
        {groups.map((g) => (
          <div key={g}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{g}</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {ACCOUNTS.filter((a) => a.group === g).map((a) => (
                <button
                  key={a.email}
                  type="button"
                  disabled={disabled}
                  onClick={() => onPick(a.email, PASSWORD)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50"
                >
                  <span className="block font-medium text-slate-800">{a.email}</span>
                  <span className="block text-xs text-slate-500">{a.note}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
