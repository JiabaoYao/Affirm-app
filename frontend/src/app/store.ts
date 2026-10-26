import { configureStore, createListenerMiddleware, isRejectedWithValue } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";

import { baseApi } from "../api/baseApi";
import authReducer, { persistAuth } from "../features/auth/authSlice";
import checkoutReducer from "../features/checkout/checkoutSlice";
import toastReducer, { toastAdded } from "../features/ui/toastSlice";
import { getErrorMessage, getHttpStatus } from "../lib/errors";

/** Any failed mutation shows an error toast, so no button fails silently. Forms still show 422s inline. */
const errorToasts = createListenerMiddleware();
errorToasts.startListening({
  matcher: isRejectedWithValue,
  effect: (action, api) => {
    const meta = action.meta as { arg?: { type?: string; endpointName?: string } };
    const isMutation = meta.arg?.type === "mutation";
    const status = getHttpStatus(action.payload);
    // 401 is handled by the session logic; login shows its own message; 422 is shown next to the inputs.
    if (!isMutation || status === 401 || status === 422 || meta.arg?.endpointName === "login") return;
    api.dispatch(toastAdded("error", getErrorMessage(action.payload)));
  },
});

export const store = configureStore({
  reducer: {
    auth: authReducer,
    checkout: checkoutReducer,
    toasts: toastReducer,
    [baseApi.reducerPath]: baseApi.reducer,
  },
  middleware: (getDefault) => getDefault().prepend(errorToasts.middleware).concat(baseApi.middleware),
});

// Enables refetchOnFocus / refetchOnReconnect (window focus and online events).
setupListeners(store.dispatch);

// Keep the session across reloads.
let lastAuth = store.getState().auth;
store.subscribe(() => {
  const auth = store.getState().auth;
  if (auth !== lastAuth) {
    lastAuth = auth;
    persistAuth(auth);
  }
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
