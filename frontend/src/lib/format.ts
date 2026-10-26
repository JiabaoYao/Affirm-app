const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return usd.format(Number(value));
}

/** "0.1000" -> "10%", "0.2850" -> "28.5%". */
export function apr(value: string | number): string {
  const pct = Math.round(Number(value) * 10000) / 100; // 0.1 * 100 is 10.000000000000002
  return `${pct}%`;
}

export function percent(value: string | number): string {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

/** Date-only strings ("2026-11-15") are local calendar dates, not UTC midnight. */
function parse(value: string): Date {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(value);
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return parse(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return parse(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function timeAgo(value: string): string {
  const seconds = Math.round((Date.now() - parse(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return date(value);
}

/** "Tablet" for one unit, "Tablet × 3" for several. */
export function item(x: { product_name: string; quantity: number }): string {
  return x.quantity > 1 ? `${x.product_name} × ${x.quantity}` : x.product_name;
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
