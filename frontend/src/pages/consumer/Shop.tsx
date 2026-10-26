import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useStoreMerchantsQuery, useStoreProductsQuery, type StoreQuery } from "../../api/storeApi";
import { useCheckoutMutation } from "../../api/transactionsApi";
import type { StoreProduct } from "../../api/types";
import { EmptyState, ErrorState, PageHeader, Pagination, Spinner } from "../../components/ui";
import { useDebounced } from "../../hooks/useDebounced";
import { money } from "../../lib/format";
import CreditCard from "./CreditCard";

const SIZE = 12;

function ProductCard({ product, onBuy, busy }: { product: StoreProduct; onBuy: () => void; busy: boolean }) {
  return (
    <div className="card flex flex-col p-5">
      <div className="mb-4 flex h-32 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 text-4xl font-bold text-slate-400">
        {product.name.charAt(0)}
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{product.merchant_name}</p>
      <h3 className="mt-1 font-semibold text-slate-900">{product.name}</h3>
      <p className="mt-1 text-lg font-bold">{money(product.price)}</p>
      <p className="mt-1 min-h-10 text-sm text-slate-600">
        {product.as_low_as_monthly ? (
          <>
            As low as <strong className="text-brand-700">{money(product.as_low_as_monthly)}/mo</strong> for {product.as_low_as_term} months
          </>
        ) : (
          <span className="text-slate-400">Financing not available for this price</span>
        )}
        {product.has_zero_apr && <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">0% APR option</span>}
      </p>
      <button className="btn-primary mt-4" onClick={onBuy} disabled={busy || !product.as_low_as_monthly}>
        {busy ? "Checking…" : "Buy with Affirm"}
      </button>
    </div>
  );
}

export default function Shop() {
  const [search, setSearch] = useState("");
  const [merchantId, setMerchantId] = useState<number | undefined>();
  const [sort, setSort] = useState<StoreQuery["sort"]>("name");
  const [page, setPage] = useState(1);
  const q = useDebounced(search);

  const merchants = useStoreMerchantsQuery();
  const products = useStoreProductsQuery({ q, merchant_id: merchantId, sort, page, size: SIZE });
  const [checkout, { isLoading, originalArgs }] = useCheckoutMutation();
  const navigate = useNavigate();

  async function buy(product: StoreProduct) {
    try {
      const tx = await checkout({ product_id: product.id }).unwrap();
      navigate(`/app/checkout/${tx.id}`);
    } catch {
      // toast from the global handler
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Shop" subtitle="Merchants that offer Affirm at checkout. Pay over time with no hidden fees." />
      <CreditCard compact />

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <input
          className="input md:max-w-xs"
          placeholder="Search products…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          aria-label="Search products"
        />
        <select
          className="input md:max-w-[12rem]"
          value={merchantId ?? ""}
          onChange={(e) => {
            setMerchantId(e.target.value ? Number(e.target.value) : undefined);
            setPage(1);
          }}
          aria-label="Filter by merchant"
        >
          <option value="">All merchants</option>
          {merchants.data?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.business_name}
            </option>
          ))}
        </select>
        <select className="input md:max-w-[12rem]" value={sort} onChange={(e) => setSort(e.target.value as StoreQuery["sort"])} aria-label="Sort">
          <option value="name">Name A–Z</option>
          <option value="price">Price: low to high</option>
          <option value="-price">Price: high to low</option>
        </select>
      </div>

      {products.isLoading ? (
        <Spinner />
      ) : products.error ? (
        <ErrorState error={products.error} onRetry={products.refetch} />
      ) : products.data!.items.length === 0 ? (
        <EmptyState title="No products found" body={q ? `Nothing matches "${q}".` : "No merchants are selling yet."} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {products.data!.items.map((p) => (
              <ProductCard key={p.id} product={p} onBuy={() => buy(p)} busy={isLoading && originalArgs?.product_id === p.id} />
            ))}
          </div>
          <Pagination page={page} size={SIZE} total={products.data!.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
