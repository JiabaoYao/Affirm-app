import { useEffect, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { useMeQuery } from "./api/authApi";
import { useAppDispatch, useAppSelector } from "./app/hooks";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Toasts from "./components/Toasts";
import { homePathFor, selectToken, selectUser, sessionExpired, userLoaded } from "./features/auth/authSlice";
import AdminDelinquency from "./pages/admin/Delinquency";
import AdminMerchants from "./pages/admin/Merchants";
import AdminOperations from "./pages/admin/Operations";
import AdminOverview from "./pages/admin/Overview";
import AdminReviews from "./pages/admin/Reviews";
import AdminRiskTiers from "./pages/admin/RiskTiers";
import Checkout from "./pages/consumer/Checkout";
import ConsumerDashboard from "./pages/consumer/Dashboard";
import LoanDetail from "./pages/consumer/LoanDetail";
import Loans from "./pages/consumer/Loans";
import Purchases from "./pages/consumer/Purchases";
import Shop from "./pages/consumer/Shop";
import Wallet from "./pages/consumer/Wallet";
import MerchantDashboard from "./pages/merchant/Dashboard";
import MerchantOrders from "./pages/merchant/Orders";
import MerchantProducts from "./pages/merchant/Products";
import MerchantPrograms from "./pages/merchant/Programs";
import Notifications from "./pages/Notifications";
import Landing from "./pages/public/Landing";
import Login from "./pages/public/Login";
import Register from "./pages/public/Register";
import { Forbidden, NotFound } from "./pages/public/StatusPages";

/** On load, re-validate a stored token and refresh the profile; sign out on its own when the JWT expires. */
function SessionBootstrap() {
  const dispatch = useAppDispatch();
  const token = useAppSelector(selectToken);
  const expiresAt = useAppSelector((s) => s.auth.expiresAt);
  const { data } = useMeQuery(undefined, { skip: !token });

  useEffect(() => {
    if (data) dispatch(userLoaded(data));
  }, [data, dispatch]);

  useEffect(() => {
    if (!expiresAt) return;
    const timer = setTimeout(
      () => dispatch(sessionExpired("Your session expired after 60 minutes. Please sign in again.")),
      Math.max(expiresAt - Date.now(), 0),
    );
    return () => clearTimeout(timer);
  }, [dispatch, expiresAt]);

  return null;
}

/** Login and register are for signed-out visitors only. */
function PublicOnly({ children }: { children: ReactNode }) {
  const user = useAppSelector(selectUser);
  return user ? <Navigate to={homePathFor(user.role)} replace /> : <>{children}</>;
}

export default function App() {
  return (
    <>
      <SessionBootstrap />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />

        {/* Everything below needs a signed-in user and shares the app chrome. */}
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/notifications" element={<Notifications />} />

          <Route path="/app" element={<ProtectedRoute roles={["consumer"]}><Outlet /></ProtectedRoute>}>
            <Route index element={<ConsumerDashboard />} />
            <Route path="shop" element={<Shop />} />
            <Route path="checkout/:id" element={<Checkout />} />
            <Route path="loans" element={<Loans />} />
            <Route path="loans/:id" element={<LoanDetail />} />
            <Route path="purchases" element={<Purchases />} />
            <Route path="wallet" element={<Wallet />} />
          </Route>

          <Route path="/merchant" element={<ProtectedRoute roles={["merchant"]}><Outlet /></ProtectedRoute>}>
            <Route index element={<MerchantDashboard />} />
            <Route path="orders" element={<MerchantOrders />} />
            <Route path="products" element={<MerchantProducts />} />
            <Route path="programs" element={<MerchantPrograms />} />
          </Route>

          <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><Outlet /></ProtectedRoute>}>
            <Route index element={<AdminOverview />} />
            <Route path="reviews" element={<AdminReviews />} />
            <Route path="merchants" element={<AdminMerchants />} />
            <Route path="risk" element={<AdminRiskTiers />} />
            <Route path="delinquency" element={<AdminDelinquency />} />
            <Route path="operations" element={<AdminOperations />} />
          </Route>

          <Route path="/403" element={<Forbidden />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toasts />
    </>
  );
}
