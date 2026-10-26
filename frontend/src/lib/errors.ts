import type { FetchBaseQueryError } from "@reduxjs/toolkit/query";

import type { ApiErrorBody } from "../api/types";

function isFetchError(err: unknown): err is FetchBaseQueryError {
  return typeof err === "object" && err !== null && "status" in err;
}

function body(err: unknown): ApiErrorBody | null {
  if (!isFetchError(err)) return null;
  const data = err.data as Partial<ApiErrorBody> | undefined;
  return data && typeof data.detail === "string" ? (data as ApiErrorBody) : null;
}

/** The backend's {detail, code} shape becomes one readable message. */
export function getErrorMessage(err: unknown): string {
  if (isFetchError(err)) {
    if (err.status === "FETCH_ERROR") return "Can't reach the server. Check your connection and try again.";
    if (err.status === "PARSING_ERROR" || err.status === "TIMEOUT_ERROR") return "The server sent an unexpected response.";
    const data = body(err);
    if (data?.errors?.length) return data.errors.map((e) => `${e.field || "request"}: ${e.message}`).join("; ");
    if (data) return data.detail;
    return `Request failed (${err.status}).`;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

export function getErrorCode(err: unknown): string | null {
  return body(err)?.code ?? null;
}

export function getHttpStatus(err: unknown): number | null {
  return isFetchError(err) && typeof err.status === "number" ? err.status : null;
}

/** 422 validation errors keyed by field name, for showing next to form inputs. */
export function getFieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  for (const e of body(err)?.errors ?? []) out[e.field] = e.message.replace(/^Value error, /, "");
  return out;
}
