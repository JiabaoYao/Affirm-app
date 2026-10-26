import { useEffect } from "react";

import { useMeQuery } from "../../api/authApi";
import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { selectUser, userLoaded } from "../../features/auth/authSlice";

/** Shown instead of the merchant dashboard until an Affirm admin approves the account. */
export default function PendingApproval() {
  const user = useAppSelector(selectUser);
  const dispatch = useAppDispatch();
  // Poll so the page unlocks by itself once the admin approves.
  const { data, refetch, isFetching } = useMeQuery(undefined, { pollingInterval: 10000 });

  useEffect(() => {
    if (data) dispatch(userLoaded(data));
  }, [data, dispatch]);

  const suspended = user?.merchant_status === "suspended";
  return (
    <div className="mx-auto max-w-xl py-12 text-center">
      <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full text-3xl ${suspended ? "bg-rose-100" : "bg-amber-100"}`}>
        {suspended ? "⛔" : "⏳"}
      </div>
      <h1 className="mt-6 text-2xl font-bold">{suspended ? "Your merchant account is suspended" : "Your application is under review"}</h1>
      <p className="mt-3 text-slate-600">
        {suspended
          ? "New Affirm checkouts are paused for your store. Contact merchant support to resolve this."
          : `Thanks for applying, ${user?.business_name}. Affirm checks every business before it can offer financing. This page unlocks as soon as you're approved.`}
      </p>
      <div className="card mt-8 p-5 text-left text-sm">
        <p className="font-semibold">What happens next</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-600">
          <li>An Affirm admin reviews your business and sets your fee rate.</li>
          <li>You choose which plans to offer (3 to 24 months, optional 0% APR promos).</li>
          <li>Shoppers see "as low as $X/mo" on your products and check out with Affirm.</li>
        </ol>
      </div>
      <button className="btn-secondary mt-6" onClick={() => refetch()} disabled={isFetching}>
        {isFetching ? "Checking…" : "Check status"}
      </button>
    </div>
  );
}
