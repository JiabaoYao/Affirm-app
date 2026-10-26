type Param = string | number | boolean | undefined | null | (string | number)[];

/** Build "?a=1&status=x&status=y". Skips empty values; arrays repeat the key, as FastAPI expects. */
export function qs(params: Record<string, Param>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.append(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}
