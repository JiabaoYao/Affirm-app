import { createSlice, nanoid, type PayloadAction } from "@reduxjs/toolkit";

export type ToastKind = "success" | "error" | "info";

export interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
}

const toastSlice = createSlice({
  name: "toasts",
  initialState: [] as Toast[],
  reducers: {
    toastAdded: {
      reducer(state, action: PayloadAction<Toast>) {
        state.push(action.payload);
        if (state.length > 4) state.shift();
      },
      prepare(kind: ToastKind, message: string) {
        return { payload: { id: nanoid(), kind, message } };
      },
    },
    toastDismissed(state, action: PayloadAction<string>) {
      return state.filter((t) => t.id !== action.payload);
    },
  },
});

export const { toastAdded, toastDismissed } = toastSlice.actions;
export default toastSlice.reducer;
