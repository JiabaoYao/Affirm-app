import { Link, Navigate } from "react-router-dom";

import { useAppSelector } from "../../app/hooks";
import { Logo } from "../../components/Layout";
import { homePathFor, selectUser } from "../../features/auth/authSlice";

const STEPS = [
  { title: "Shop", body: "Pick something from a merchant that offers Affirm at checkout." },
  { title: "Get a real-time decision", body: "A soft credit check never hurts your score. See your spending power instantly." },
  { title: "Choose your plan", body: "Compare 3 to 24 months. The total cost is shown upfront, with no hidden fees." },
  { title: "Pay over time", body: "Autopay, extra payments or pay off early. There's never a prepayment fee." },
];

const ROLES = [
  { title: "Shoppers", body: "Check out with Affirm, compare plans, manage loans, autopay and payment methods." },
  { title: "Merchants", body: "Set your financing programs and 0% promos. Capture orders when they ship and track payouts." },
  { title: "Affirm ops", body: "Approve merchants, tune risk tiers, review flagged applications and watch delinquency." },
];

export default function Landing() {
  const user = useAppSelector(selectUser);
  if (user) return <Navigate to={homePathFor(user.role)} replace />;

  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 via-white to-white">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Logo />
        <div className="flex gap-2">
          <Link to="/login" className="btn-ghost">
            Sign in
          </Link>
          <Link to="/register" className="btn-primary">
            Get started
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 pb-16 pt-12 sm:pt-20">
        <p className="mb-4 inline-block rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold text-brand-700">
          A demo of Affirm-style installment financing
        </p>
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-6xl">
          Buy now, pay over time.{" "}
          <span className="text-brand-600">No hidden fees.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-slate-600">
          Split a purchase into fixed monthly payments. You see the APR, the monthly amount and the total cost before you
          commit, and the amount you agree to is the most you'll ever pay.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/register" className="btn-primary px-6 py-3 text-base">
            Create an account
          </Link>
          <Link to="/login" className="btn-secondary px-6 py-3 text-base">
            Try a demo account
          </Link>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <div key={s.title} className="card p-5">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white">{i + 1}</span>
              <h3 className="mt-3 font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-slate-500">{s.body}</p>
            </div>
          ))}
        </div>

        <h2 className="mt-16 text-xl font-bold">One platform, three sides</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r.title} className="rounded-2xl bg-slate-900 p-5 text-white">
              <h3 className="font-semibold">{r.title}</h3>
              <p className="mt-1 text-sm text-slate-300">{r.body}</p>
            </div>
          ))}
        </div>
      </section>
      <footer className="border-t border-slate-100 py-6 text-center text-xs text-slate-400">
        Student demo project. Not affiliated with Affirm, Inc. All credit decisions and payments are simulated.
      </footer>
    </div>
  );
}
