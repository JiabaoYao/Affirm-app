import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type { Page, PlanDetail, PlanOptions, SelectPlanIn, Transaction, TransactionStatus } from "./types";

export interface TransactionQuery {
  status?: TransactionStatus[];
  sort?: "created_at" | "-created_at" | "amount" | "-amount";
  min_amount?: string;
  max_amount?: string;
  page?: number;
  size?: number;
}

export const transactionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listTransactions: build.query<Page<Transaction>, TransactionQuery>({
      query: (params) => `/transactions${qs({ ...params })}`,
      providesTags: (result) => [
        { type: "Transaction", id: "LIST" },
        ...(result?.items.map((t) => ({ type: "Transaction" as const, id: t.id })) ?? []),
      ],
    }),
    getTransaction: build.query<Transaction, number>({
      query: (id) => `/transactions/${id}`,
      providesTags: (_r, _e, id) => [{ type: "Transaction", id }],
    }),
    checkout: build.mutation<Transaction, { product_id: number }>({
      query: (body) => ({ url: "/transactions", method: "POST", body }),
      invalidatesTags: [{ type: "Transaction", id: "LIST" }, "Credit"],
    }),
    planOptions: build.query<PlanOptions, number>({
      query: (id) => `/transactions/${id}/plan-options`,
      providesTags: (_r, _e, id) => [{ type: "Transaction", id }],
    }),
    selectPlan: build.mutation<PlanDetail, { id: number; body: SelectPlanIn }>({
      query: ({ id, body }) => ({ url: `/transactions/${id}/plan`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Transaction", id },
        { type: "Transaction", id: "LIST" },
        { type: "Plan", id: "LIST" },
        "Credit",
      ],
    }),
    cancelTransaction: build.mutation<Transaction, number>({
      query: (id) => ({ url: `/transactions/${id}/cancel`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [{ type: "Transaction", id }, { type: "Transaction", id: "LIST" }],
    }),
    captureOrder: build.mutation<Transaction, number>({
      query: (id) => ({ url: `/transactions/${id}/capture`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Transaction", id },
        { type: "Transaction", id: "LIST" },
        "MerchantSummary",
        "Metrics",
      ],
    }),
    voidOrder: build.mutation<Transaction, number>({
      query: (id) => ({ url: `/transactions/${id}/void`, method: "POST" }),
      invalidatesTags: (_r, _e, id) => [
        { type: "Transaction", id },
        { type: "Transaction", id: "LIST" },
        "MerchantSummary",
        "Metrics",
      ],
    }),
    updateTracking: build.mutation<Transaction, { id: number; tracking_number: string }>({
      query: ({ id, tracking_number }) => ({ url: `/transactions/${id}`, method: "PATCH", body: { tracking_number } }),
      invalidatesTags: (_r, _e, { id }) => [{ type: "Transaction", id }],
    }),
  }),
});

export const {
  useListTransactionsQuery,
  useGetTransactionQuery,
  useCheckoutMutation,
  usePlanOptionsQuery,
  useSelectPlanMutation,
  useCancelTransactionMutation,
  useCaptureOrderMutation,
  useVoidOrderMutation,
  useUpdateTrackingMutation,
} = transactionsApi;
