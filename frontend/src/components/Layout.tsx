import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { baseApi } from "../api/baseApi";
import { useNotificationsQuery } from "../api/notificationsApi";
import type { Role } from "../api/types";
import { useAppDispatch, useAppSelector } from "../app/hooks";
import { homePathFor, selectUser } from "../features/auth/authSlice";
import { signOut } from "../features/auth/authThunks";

const NAV: Record<Role, { to: string; label: string; end?: boolean }[]> = {
  consumer: [
    { to: "/app", label: "Home", end: true },
    { to: "/app/shop", label: "Shop" },
    { to: "/app/loans", label: "My loans" },
    { to: "/app/purchases", label: "Purchases" },
    { to: "/app/wallet", label: "Wallet" },
  ],
  merchant: [
    { to: "/merchant", label: "Dashboard", end: true },
    { to: "/merchant/orders", label: "Orders" },
    { to: "/merchant/products", label: "Products" },
    { to: "/merchant/programs", label: "Financing" },
  ],
  admin: [
    { to: "/admin", label: "Overview", end: true },
    { to: "/admin/reviews", label: "Reviews" },
    { to: "/admin/merchants", label: "Merchants" },
    { to: "/admin/risk", label: "Risk tiers" },
    { to: "/admin/delinquency", label: "Delinquency" },
    { to: "/admin/operations", label: "Operations" },
  ],
};

const ROLE_LABEL: Record<Role, string> = { consumer: "Shopper", merchant: "Merchant", admin: "Affirm ops" };

export function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 font-bold tracking-tight text-slate-900">
      <img src="/favicon.svg" alt="" className="h-7 w-7" />
      <span className="text-lg">
        mini<span className="text-brand-600">affirm</span>
      </span>
    </Link>
  );
}

function NotificationBell() {
  // Polling keeps the badge fresh: e.g. a shopper sees "order shipped" soon after the merchant captures.
  const { data } = useNotificationsQuery({ size: 1 }, { pollingInterval: 15000 });
  const unread = data?.unread ?? 0;
  const dispatch = useAppDispatch();
  // undefined = not loaded yet; null = loaded, the user has no notifications so far.
  const latestId = useRef<number | null | undefined>(undefined);

  // A new notification means another user changed our data (e.g. the merchant captured our order), and
  // tag invalidation only covers this browser's own mutations, so refetch what those events touch.
  useEffect(() => {
    if (!data) return;
    const newest = data.items[0]?.id ?? null;
    if (latestId.current !== undefined && newest !== null && newest !== latestId.current) {
      dispatch(baseApi.util.invalidateTags(["Plan", "Transaction", "Credit", "MerchantSummary", "Me"]));
    }
    latestId.current = newest;
  }, [data, dispatch]);
  return (
    <Link to="/notifications" className="btn-ghost relative px-2.5" aria-label={`Notifications (${unread} unread)`}>
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" strokeLinejoin="round" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" strokeLinecap="round" />
      </svg>
      {unread > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Link>
  );
}

function UserMenu() {
  const user = useAppSelector(selectUser);
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  if (!user) return null;
  const initials = (user.full_name || user.email).split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button className="flex items-center gap-2 rounded-full p-1 hover:bg-slate-100" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">{initials}</span>
        <span className="hidden text-left text-xs leading-tight sm:block">
          <span className="block font-semibold text-slate-800">{user.business_name ?? user.full_name}</span>
          <span className="block text-slate-500">{ROLE_LABEL[user.role]}</span>
        </span>
      </button>
      {open && (
        <div className="card absolute right-0 z-40 mt-2 w-60 p-2 text-sm">
          <div className="px-3 py-2">
            <p className="font-semibold">{user.full_name}</p>
            <p className="truncate text-slate-500">{user.email}</p>
          </div>
          <hr className="my-1 border-slate-100" />
          <button
            className="w-full rounded-lg px-3 py-2 text-left text-rose-700 hover:bg-rose-50"
            onClick={async () => {
              await dispatch(signOut());
              navigate("/login", { replace: true });
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const user = useAppSelector(selectUser);
  const links = user ? NAV[user.role] : [];
  const showNav = !(user?.role === "merchant" && user.merchant_status !== "active");

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4">
          <Logo to={user ? homePathFor(user.role) : "/"} />
          {showNav && (
            <nav className="hidden flex-1 gap-1 md:flex">
              {links.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.end}
                  className={({ isActive }) =>
                    `rounded-full px-3 py-1.5 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:text-slate-900"}`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-1">
            <NotificationBell />
            <UserMenu />
          </div>
        </div>
        {showNav && (
          <nav className="flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-slate-600"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
