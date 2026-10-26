import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useRegisterMutation } from "../../api/authApi";
import { useAppDispatch } from "../../app/hooks";
import { Alert, Field, FilterChips } from "../../components/ui";
import { homePathFor } from "../../features/auth/authSlice";
import { signIn } from "../../features/auth/authThunks";
import { toastAdded } from "../../features/ui/toastSlice";
import { getErrorCode, getErrorMessage, getFieldErrors } from "../../lib/errors";
import AuthShell from "./AuthShell";

type Kind = "consumer" | "merchant";

export default function Register() {
  const [kind, setKind] = useState<Kind>("consumer");
  const [form, setForm] = useState({ full_name: "", email: "", password: "", business_name: "" });
  const [register, { isLoading, error }] = useRegisterMutation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const fieldErrors = getFieldErrors(error);
  const generalError = error && Object.keys(fieldErrors).length === 0 ? getErrorMessage(error) : null;

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await register({
        role: kind,
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        business_name: kind === "merchant" ? form.business_name : undefined,
      }).unwrap();
    } catch {
      return;
    }
    const result = await dispatch(signIn({ email: form.email, password: form.password }));
    if (signIn.fulfilled.match(result)) {
      dispatch(toastAdded("success", kind === "merchant" ? "Application submitted! An Affirm admin will review it." : "Welcome to mini-affirm!"));
      navigate(homePathFor(result.payload.role), { replace: true });
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Shop now and pay over time, or offer Affirm to your customers.">
      <div className="mb-5">
        <FilterChips<Kind>
          value={kind}
          onChange={setKind}
          options={[
            { value: "consumer", label: "I'm shopping" },
            { value: "merchant", label: "I'm a business" },
          ]}
        />
      </div>
      {kind === "merchant" && (
        <div className="mb-4">
          <Alert>Merchant accounts start as pending. An Affirm admin approves them before you can sell.</Alert>
        </div>
      )}
      {generalError && (
        <div className="mb-4">
          <Alert kind="error">
            {generalError}
            {getErrorCode(error) === "EMAIL_TAKEN" && (
              <>
                {" "}
                <Link to="/login" className="font-semibold underline">
                  Sign in instead
                </Link>
              </>
            )}
          </Alert>
        </div>
      )}
      <form onSubmit={submit} className="space-y-4">
        <Field label="Full name" value={form.full_name} onChange={set("full_name")} error={fieldErrors.full_name} required maxLength={100} autoComplete="name" />
        {kind === "merchant" && (
          <Field label="Business name" value={form.business_name} onChange={set("business_name")} error={fieldErrors.business_name ?? fieldErrors[""]} required maxLength={120} />
        )}
        <Field label="Email" type="email" value={form.email} onChange={set("email")} error={fieldErrors.email} required autoComplete="email" />
        <Field
          label="Password"
          type="password"
          value={form.password}
          onChange={set("password")}
          error={fieldErrors.password}
          hint="At least 8 characters."
          minLength={8}
          maxLength={72}
          required
          autoComplete="new-password"
        />
        <button className="btn-primary w-full py-2.5" disabled={isLoading}>
          {isLoading ? "Creating account…" : kind === "merchant" ? "Apply to become a merchant" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link to="/login" className="font-semibold text-brand-700 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
