import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { Role, User } from "../../api/types";

export interface AuthState {
  token: string | null;
  /** Epoch ms when the JWT expires; the app signs out on its own at that moment. */
  expiresAt: number | null;
  user: User | null;
  /** Shown on the login page after a forced sign-out (expired or revoked token). */
  notice: string | null;
}

const STORAGE_KEY = "mini-affirm.auth";

function loadInitialState(): AuthState {
  const empty: AuthState = { token: null, expiresAt: null, user: null, notice: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return empty;
    const saved = JSON.parse(raw) as Pick<AuthState, "token" | "expiresAt" | "user">;
    if (!saved.token || !saved.expiresAt || saved.expiresAt <= Date.now()) return empty;
    return { ...empty, ...saved };
  } catch {
    return empty;
  }
}

export function persistAuth(state: AuthState): void {
  try {
    if (state.token) {
      const { token, expiresAt, user } = state;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, expiresAt, user }));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage blocked (private mode): the session just won't survive a reload.
  }
}

const authSlice = createSlice({
  name: "auth",
  initialState: loadInitialState,
  reducers: {
    signedIn(state, action: PayloadAction<{ token: string; expiresIn: number }>) {
      state.token = action.payload.token;
      state.expiresAt = Date.now() + action.payload.expiresIn * 1000;
      state.notice = null;
    },
    userLoaded(state, action: PayloadAction<User>) {
      state.user = action.payload;
    },
    signedOut(state) {
      state.token = null;
      state.expiresAt = null;
      state.user = null;
    },
    sessionExpired(state, action: PayloadAction<string>) {
      state.token = null;
      state.expiresAt = null;
      state.user = null;
      state.notice = action.payload;
    },
    noticeCleared(state) {
      state.notice = null;
    },
  },
});

export const { signedIn, userLoaded, signedOut, sessionExpired, noticeCleared } = authSlice.actions;
export default authSlice.reducer;

type WithAuth = { auth: AuthState };
export const selectToken = (s: WithAuth) => s.auth.token;
export const selectUser = (s: WithAuth) => s.auth.user;
export const selectIsAuthenticated = (s: WithAuth) => Boolean(s.auth.token);

export function homePathFor(role: Role): string {
  return role === "admin" ? "/admin" : role === "merchant" ? "/merchant" : "/app";
}
