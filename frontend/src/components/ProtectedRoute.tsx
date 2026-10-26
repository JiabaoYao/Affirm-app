import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import type { Role } from "../api/types";
import { useAppSelector } from "../app/hooks";
import { selectToken, selectUser } from "../features/auth/authSlice";
import PendingApproval from "../pages/merchant/PendingApproval";
import { Spinner } from "./ui";

/**
 * Guards a route tree:
 *  - signed out      -> /login, remembering where the user was going
 *  - wrong role      -> /403
 *  - merchant not yet approved -> the "pending approval" page instead of the dashboard
 */
export default function ProtectedRoute({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const token = useAppSelector(selectToken);
  const user = useAppSelector(selectUser);
  const location = useLocation();

  if (!token) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (!user) return <Spinner label="Loading your account…" />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/403" replace />;
  if (user.role === "merchant" && user.merchant_status !== "active" && roles?.includes("merchant")) {
    return <PendingApproval />;
  }
  return <>{children}</>;
}
