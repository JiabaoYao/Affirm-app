import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type { Page, Payment, PaymentResult, PlanDetail, PlanStatus, PlanSummary, PlanUpdate } from "./types";

export const plansApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listPlans: build.query<Page<PlanSummary>, { status?: PlanStatus[]; page?: number; size?: number }>({
      query: (params) => `/plans${qs({ ...params })}`,
      providesTags: (result) => [
        { type: "Plan", id: "LIST" },
        ...(result?.items.map((p) => ({ type: "Plan" as const, id: p.id })) ?? []),
      ],
    }),
    getPlan: build.query<PlanDetail, number>({
      query: (id) => `/plans/${id}`,
      providesTags: (_r, _e, id) => [{ type: "Plan", id }],
    }),
    updatePlan: build.mutation<PlanDetail, { id: number; body: PlanUpdate }>({
      query: ({ id, body }) => ({ url: `/plans/${id}`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, { id }) => [{ type: "Plan", id }, { type: "Plan", id: "LIST" }],
    }),
    makePayment: build.mutation<PaymentResult, { id: number; amount: string; payment_method_id?: number }>({
      query: ({ id, ...body }) => ({ url: `/plans/${id}/payments`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => [
        { type: "Plan", id },
        { type: "Plan", id: "LIST" },
        "Credit",
        "Notification",
      ],
    }),
    listPayments: build.query<Payment[], number>({
      query: (id) => `/plans/${id}/payments`,
      providesTags: (_r, _e, id) => [{ type: "Plan", id }],
    }),
  }),
});

export const {
  useListPlansQuery,
  useGetPlanQuery,
  useUpdatePlanMutation,
  useMakePaymentMutation,
  useListPaymentsQuery,
} = plansApi;
