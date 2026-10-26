import { baseApi } from "./baseApi";
import type { PaymentMethod, PaymentMethodIn } from "./types";

export const walletApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    paymentMethods: build.query<PaymentMethod[], void>({
      query: () => "/payment-methods",
      providesTags: ["PaymentMethod"],
    }),
    addPaymentMethod: build.mutation<PaymentMethod, PaymentMethodIn>({
      query: (body) => ({ url: "/payment-methods", method: "POST", body }),
      invalidatesTags: ["PaymentMethod"],
    }),
    makeDefaultMethod: build.mutation<PaymentMethod, number>({
      query: (id) => ({ url: `/payment-methods/${id}/default`, method: "POST" }),
      invalidatesTags: ["PaymentMethod"],
    }),
    removePaymentMethod: build.mutation<void, number>({
      query: (id) => ({ url: `/payment-methods/${id}`, method: "DELETE" }),
      // Plans that autopaid from it get a new method, so refetch them too.
      invalidatesTags: ["PaymentMethod", "Plan"],
    }),
  }),
});

export const {
  usePaymentMethodsQuery,
  useAddPaymentMethodMutation,
  useMakeDefaultMethodMutation,
  useRemovePaymentMethodMutation,
} = walletApi;
