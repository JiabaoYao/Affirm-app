import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type { Credit, Page, StoreMerchant, StoreProduct } from "./types";

export interface StoreQuery {
  q?: string;
  merchant_id?: number;
  sort?: "name" | "-name" | "price" | "-price";
  page?: number;
  size?: number;
}

export const storeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    storeProducts: build.query<Page<StoreProduct>, StoreQuery>({
      query: (params) => `/store/products${qs({ ...params })}`,
      providesTags: ["Store"],
    }),
    storeMerchants: build.query<StoreMerchant[], void>({
      query: () => "/store/merchants",
      providesTags: ["Store"],
    }),
    myCredit: build.query<Credit, void>({
      query: () => "/credit/me",
      providesTags: ["Credit"],
    }),
    checkCredit: build.mutation<Credit, void>({
      query: () => ({ url: "/credit/check", method: "POST" }),
      invalidatesTags: ["Credit"],
    }),
  }),
});

export const { useStoreProductsQuery, useStoreMerchantsQuery, useMyCreditQuery, useCheckCreditMutation } = storeApi;
