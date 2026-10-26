import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { Alert, Field } from "../../components/ui";
import { homePathFor, noticeCleared } from "../../features/auth/authSlice";
import { signIn } from "../../features/auth/authThunks";
import { getErrorMessage } from "../../lib/errors";
import AuthShell from "./AuthShell";
import DemoAccounts from "./DemoAccounts";

export default function Login() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const notice = useAppSelector((s) => s.auth.notice);
  const from = (location.state as { from?: string } | null)?.from;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => () => void dispatch(noticeCleared()), [dispatch]);

  async function login(emailValue: string, passwordValue: string) {
    setBusy(true);
    setError(null);
    const result = await dispatch(signIn({ email: emailValue, password: passwordValue }));
    setBusy(false);
    if (signIn.fulfilled.match(result)) {
      const home = homePathFor(result.payload.role);
      // Only go back to the page they wanted if it belongs to their role's area.
      navigate(from && (from.startsWith(home) || from === "/notifications") ? from : home, { replace: true });
    } else {
      setError(getErrorMessage(result.payload));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void login(email, password);
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to manage your payments, orders or operations.">
      <div className="space-y-4">
        {notice && <Alert kind="warning">{notice}</Alert>}
        {from && !notice && <Alert>Please sign in to continue.</Alert>}
        {error && <Alert kind="error">{error}</Alert>}
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Field
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button className="btn-primary w-full py-2.5" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="text-center text-sm text-slate-500">
          New here?{" "}
          <Link to="/register" className="font-semibold text-brand-700 hover:underline">
            Create an account
          </Link>
        </p>
        <DemoAccounts onPick={(demoEmail, demoPassword) => void login(demoEmail, demoPassword)} disabled={busy} />
      </div>
    </AuthShell>
  );
}
