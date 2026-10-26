import { baseApi } from "./baseApi";
import { qs } from "./qs";
import type { MerchantSummary, Page, Product, Program, ProgramIn } from "./types";

export const merchantApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    myProducts: build.query<Page<Product>, { q?: string; sort?: string; page?: number; size?: number }>({
      query: (params) => `/products${qs({ ...params })}`,
      providesTags: ["Product"],
    }),
    createProduct: build.mutation<Product, { name: string; price: string }>({
      query: (body) => ({ url: "/products", method: "POST", body }),
      invalidatesTags: ["Product", "Store"],
    }),
    updateProduct: build.mutation<Product, { id: number; name?: string; price?: string }>({
      query: ({ id, ...body }) => ({ url: `/products/${id}`, method: "PATCH", body }),
      invalidatesTags: ["Product", "Store"],
    }),
    programs: build.query<Program[], void>({
      query: () => "/merchant/programs",
      providesTags: ["Program"],
    }),
    createProgram: build.mutation<Program, ProgramIn>({
      query: (body) => ({ url: "/merchant/programs", method: "POST", body }),
      invalidatesTags: ["Program", "Store"],
    }),
    updateProgram: build.mutation<Program, { id: number } & Partial<Omit<ProgramIn, "term_months">>>({
      query: ({ id, ...body }) => ({ url: `/merchant/programs/${id}`, method: "PATCH", body }),
      invalidatesTags: ["Program", "Store"],
    }),
    merchantSummary: build.query<MerchantSummary, void>({
      query: () => "/merchant/summary",
      providesTags: ["MerchantSummary"],
    }),
  }),
});

export const {
  useMyProductsQuery,
  useCreateProductMutation,
  useUpdateProductMutation,
  useProgramsQuery,
  useCreateProgramMutation,
  useUpdateProgramMutation,
  useMerchantSummaryQuery,
} = merchantApi;
