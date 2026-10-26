import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";

import { config } from "../config";
import { sessionExpired } from "../features/auth/authSlice";

interface StateWithToken {
  auth: { token: string | null };
}

const rawBaseQuery = fetchBaseQuery({
  baseUrl: config.apiBaseUrl,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as StateWithToken).auth.token;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

/** Every request goes through here: a 401 on a signed-in request means the token expired or was revoked. */
const baseQueryWithAuth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  const result = await rawBaseQuery(args, api, extraOptions);
  const hadToken = Boolean((api.getState() as StateWithToken).auth.token);
  if (result.error?.status === 401 && hadToken) {
    api.dispatch(sessionExpired("Your session has ended. Please sign in again."));
    api.dispatch(baseApi.util.resetApiState());
  }
  return result;
};

/** One API slice; each feature adds its endpoints with injectEndpoints. Tags drive cache invalidation. */
export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithAuth,
  tagTypes: [
    "Me",
    "Credit",
    "Store",
    "Transaction",
    "Plan",
    "PaymentMethod",
    "Notification",
    "Product",
    "Program",
    "MerchantSummary",
    "AdminMerchant",
    "RiskTier",
    "Review",
    "Metrics",
    "Delinquency",
    "Audit",
  ],
  endpoints: () => ({}),
});
