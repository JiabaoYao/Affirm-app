import type { Transaction } from "../../api/types";
import { StatusBadge, TableCard } from "../../components/ui";
import { date, money } from "../../lib/format";
import OrderActions from "./OrderActions";

export default function OrdersTable({ orders }: { orders: Transaction[] }) {
  return (
    <TableCard>
      <table className="table-base">
        <thead className="bg-slate-50">
          <tr>
            <th>Order</th>
            <th>Customer</th>
            <th>Product</th>
            <th className="text-right">Amount</th>
            <th className="text-right">Fee</th>
            <th>Status</th>
            <th className="text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {orders.map((o) => (
            <tr key={o.id}>
              <td>
                <p className="font-medium text-slate-900">#{o.id}</p>
                <p className="text-xs text-slate-500">{date(o.created_at)}</p>
              </td>
              <td>
                <p className="text-slate-900">{o.customer_name || "—"}</p>
                <p className="text-xs text-slate-500">{o.customer_email}</p>
              </td>
              <td>
                {o.product_name}
                {o.tracking_number && <p className="text-xs text-slate-500">Tracking {o.tracking_number}</p>}
              </td>
              <td className="text-right font-medium">{money(o.amount)}</td>
              <td className="text-right text-slate-500">{money(o.merchant_fee)}</td>
              <td>
                <StatusBadge status={o.status} />
              </td>
              <td>
                <OrderActions order={o} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableCard>
  );
}
