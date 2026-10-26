import { baseApi } from "./baseApi";
import type { RegisterIn, TokenOut, User } from "./types";

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // OAuth2 password form: the email goes in `username`, sent form-encoded.
    login: build.mutation<TokenOut, { email: string; password: string }>({
      query: ({ email, password }) => ({
        url: "/auth/login",
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
      }),
    }),
    register: build.mutation<User, RegisterIn>({
      query: (body) => ({ url: "/auth/register", method: "POST", body }),
    }),
    logout: build.mutation<void, void>({
      query: () => ({ url: "/auth/logout", method: "POST" }),
    }),
    me: build.query<User, void>({
      query: () => "/auth/me",
      providesTags: ["Me"],
    }),
  }),
});

export const { useLoginMutation, useRegisterMutation, useMeQuery } = authApi;
