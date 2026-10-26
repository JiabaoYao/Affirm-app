import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type {
  AdminMerchant,
  AuditEntry,
  DelinquencyBucket,
  DelinquentLoan,
  MerchantStatus,
  Metrics,
  Page,
  RiskTier,
  RunDailyOut,
  Transaction,
} from "./types";

export const adminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    adminMerchants: build.query<Page<AdminMerchant>, { status?: MerchantStatus; page?: number }>({
      query: (params) => `/admin/merchants${qs({ ...params })}`,
      providesTags: ["AdminMerchant"],
    }),
    approveMerchant: build.mutation<AdminMerchant, { id: number; fee_rate?: string; promo_fee_rate?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/merchants/${id}/approve`, method: "POST", body }),
      invalidatesTags: ["AdminMerchant", "Metrics", "Store", "Audit"],
    }),
    suspendMerchant: build.mutation<AdminMerchant, number>({
      query: (id) => ({ url: `/admin/merchants/${id}/suspend`, method: "POST" }),
      invalidatesTags: ["AdminMerchant", "Metrics", "Store", "Audit"],
    }),
    riskTiers: build.query<RiskTier[], void>({
      query: () => "/admin/risk-tiers",
      providesTags: ["RiskTier"],
    }),
    updateRiskTier: build.mutation<RiskTier, { id: number } & Partial<Omit<RiskTier, "id" | "name">>>({
      query: ({ id, ...body }) => ({ url: `/admin/risk-tiers/${id}`, method: "PATCH", body }),
      invalidatesTags: ["RiskTier", "Store", "Audit"],
    }),
    reviews: build.query<Page<Transaction>, { page?: number }>({
      query: (params) => `/admin/reviews${qs({ ...params })}`,
      providesTags: ["Review"],
    }),
    decideReview: build.mutation<Transaction, { id: number; approve: boolean; reason?: string }>({
      query: ({ id, approve, reason }) => ({
        url: `/admin/reviews/${id}/${approve ? "approve" : "decline"}`,
        method: "POST",
        body: { reason: reason || null },
      }),
      invalidatesTags: ["Review", "Metrics", "Audit", { type: "Transaction", id: "LIST" }],
    }),
    delinquency: build.query<DelinquentLoan[], { bucket?: DelinquencyBucket }>({
      query: (params) => `/admin/delinquency${qs({ ...params })}`,
      providesTags: ["Delinquency"],
    }),
    metrics: build.query<Metrics, void>({
      query: () => "/admin/metrics",
      providesTags: ["Metrics"],
    }),
    runDaily: build.mutation<RunDailyOut, { as_of?: string }>({
      query: (body) => ({ url: "/admin/jobs/run-daily", method: "POST", body }),
      invalidatesTags: ["Delinquency", "Metrics", "Audit", "Plan"],
    }),
    auditLog: build.query<Page<AuditEntry>, { page?: number; size?: number }>({
      query: (params) => `/admin/audit-log${qs({ ...params })}`,
      providesTags: ["Audit"],
    }),
  }),
});

export const {
  useAdminMerchantsQuery,
  useApproveMerchantMutation,
  useSuspendMerchantMutation,
  useRiskTiersQuery,
  useUpdateRiskTierMutation,
  useReviewsQuery,
  useDecideReviewMutation,
  useDelinquencyQuery,
  useMetricsQuery,
  useRunDailyMutation,
  useAuditLogQuery,
} = adminApi;
