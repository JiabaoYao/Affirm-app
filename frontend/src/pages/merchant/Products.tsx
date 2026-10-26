import { useState, type FormEvent } from "react";

import { useCreateProductMutation, useMyProductsQuery, useUpdateProductMutation } from "../../api/merchantApi";
import type { Product } from "../../api/types";
import { useAppDispatch } from "../../app/hooks";
import { EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, Spinner, TableCard } from "../../components/ui";
import { toastAdded } from "../../features/ui/toastSlice";
import { useDebounced } from "../../hooks/useDebounced";
import { getFieldErrors } from "../../lib/errors";
import { date, money } from "../../lib/format";

const SIZE = 10;

function ProductForm({ product, onDone }: { product?: Product; onDone: () => void }) {
  const [name, setName] = useState(product?.name ?? "");
  const [price, setPrice] = useState(product?.price ?? "");
  const [create, createState] = useCreateProductMutation();
  const [update, updateState] = useUpdateProductMutation();
  const dispatch = useAppDispatch();
  const state = product ? updateState : createState;
  const errors = getFieldErrors(state.error);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (product) await update({ id: product.id, name, price }).unwrap();
      else await create({ name, price }).unwrap();
      dispatch(toastAdded("success", product ? "Product updated." : `${name} is now in the Affirm store.`));
      onDone();
    } catch {
      // inline (422) or toast
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Name" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} required maxLength={200} />
      <Field
        label="Price (USD)"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        error={errors.price}
        inputMode="decimal"
        placeholder="499.00"
        hint="Affirm finances purchases from $50 to $30,000, within your programs' limits."
        required
      />
      <button className="btn-primary w-full" disabled={state.isLoading}>
        {product ? "Save changes" : "Add product"}
      </button>
    </form>
  );
}

export default function Products() {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const q = useDebounced(search);
  const { data, isLoading, error, refetch } = useMyProductsQuery({ q, sort, page, size: SIZE });

  return (
    <div>
      <PageHeader
        title="Products"
        subtitle="Your catalog. Shoppers see these in the Affirm store with 'as low as' pricing."
        actions={
          <button className="btn-primary" onClick={() => setEditing("new")}>
            Add product
          </button>
        }
      />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row">
        <input className="input sm:max-w-xs" placeholder="Search…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} aria-label="Search products" />
        <select className="input sm:max-w-[12rem]" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          <option value="name">Name A–Z</option>
          <option value="-price">Price: high to low</option>
          <option value="price">Price: low to high</option>
          <option value="-created_at">Newest</option>
        </select>
      </div>
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data!.items.length === 0 ? (
        <EmptyState title={q ? "No matches" : "No products yet"} body={q ? `Nothing matches "${q}".` : "Add your first product to start selling with Affirm."} />
      ) : (
        <>
          <TableCard>
            <table className="table-base">
              <thead className="bg-slate-50">
                <tr>
                  <th>Name</th>
                  <th className="text-right">Price</th>
                  <th>Added</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data!.items.map((p) => (
                  <tr key={p.id}>
                    <td className="font-medium text-slate-900">{p.name}</td>
                    <td className="text-right">{money(p.price)}</td>
                    <td>{date(p.created_at)}</td>
                    <td className="text-right">
                      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setEditing(p)}>
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableCard>
          <Pagination page={page} size={SIZE} total={data!.total} onPage={setPage} />
        </>
      )}
      <Modal open={editing !== null} title={editing === "new" ? "Add product" : "Edit product"} onClose={() => setEditing(null)}>
        {editing !== null && <ProductForm product={editing === "new" ? undefined : editing} onDone={() => setEditing(null)} />}
      </Modal>
    </div>
  );
}
