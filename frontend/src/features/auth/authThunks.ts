import { createAsyncThunk } from "@reduxjs/toolkit";

import { authApi } from "../../api/authApi";
import { baseApi } from "../../api/baseApi";
import type { User } from "../../api/types";
import { signedIn, signedOut, userLoaded } from "./authSlice";

/** Log in, store the token, then load the profile (role, merchant status) that routing depends on. */
export const signIn = createAsyncThunk<User, { email: string; password: string }>(
  "auth/signIn",
  async (credentials, { dispatch, rejectWithValue }) => {
    try {
      const token = await dispatch(authApi.endpoints.login.initiate(credentials)).unwrap();
      dispatch(signedIn({ token: token.access_token, expiresIn: token.expires_in }));
      const user = await dispatch(authApi.endpoints.me.initiate(undefined, { forceRefetch: true })).unwrap();
      dispatch(userLoaded(user));
      return user;
    } catch (err) {
      dispatch(signedOut());
      return rejectWithValue(err);
    }
  },
);

/** Revoke the token on the server (best effort), then clear the session and every cached response. */
export const signOut = createAsyncThunk("auth/signOut", async (_: void, { dispatch }) => {
  try {
    await dispatch(authApi.endpoints.logout.initiate()).unwrap();
  } catch {
    // Already expired or offline: signing out locally is still correct.
  }
  dispatch(signedOut());
  dispatch(baseApi.util.resetApiState());
});
