import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

/** Client-side state of the multi-step checkout wizard. Server data (offers, decision) lives in RTK Query. */
export type CheckoutStep = "plans" | "review" | "done";

export interface CheckoutState {
  transactionId: number | null;
  step: CheckoutStep;
  termMonths: number | null;
  autopayEnabled: boolean;
  autopayDay: number;
  paymentMethodId: number | null;
  agreed: boolean;
}

const initialState: CheckoutState = {
  transactionId: null,
  step: "plans",
  termMonths: null,
  autopayEnabled: true,
  autopayDay: Math.min(new Date().getDate(), 28),
  paymentMethodId: null,
  agreed: false,
};

const checkoutSlice = createSlice({
  name: "checkout",
  initialState,
  reducers: {
    checkoutStarted(state, action: PayloadAction<number>) {
      if (state.transactionId !== action.payload) return { ...initialState, transactionId: action.payload };
    },
    termChosen(state, action: PayloadAction<number>) {
      state.termMonths = action.payload;
      state.step = "review";
      state.agreed = false;
    },
    autopayToggled(state, action: PayloadAction<boolean>) {
      state.autopayEnabled = action.payload;
    },
    autopayDayChanged(state, action: PayloadAction<number>) {
      state.autopayDay = action.payload;
    },
    paymentMethodChosen(state, action: PayloadAction<number | null>) {
      state.paymentMethodId = action.payload;
    },
    agreementToggled(state, action: PayloadAction<boolean>) {
      state.agreed = action.payload;
    },
    stepChanged(state, action: PayloadAction<CheckoutStep>) {
      state.step = action.payload;
    },
    checkoutReset() {
      return initialState;
    },
  },
});

export const {
  checkoutStarted,
  termChosen,
  autopayToggled,
  autopayDayChanged,
  paymentMethodChosen,
  agreementToggled,
  stepChanged,
  checkoutReset,
} = checkoutSlice.actions;
export default checkoutSlice.reducer;
