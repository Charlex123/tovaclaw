import { Package, Truck, CheckCircle, XCircle, Clock } from "lucide-react";

interface OrderItem {
  name: string;
  quantity: number;
  price: string;
}

interface OrderData {
  order_id: string;
  status: "pending" | "processing" | "shipped" | "delivered" | "cancelled";
  items: OrderItem[];
  total: string;
  estimated_delivery?: string;
}

const statusConfig = {
  pending: { icon: Clock, color: "text-amber-400", label: "Pending" },
  processing: { icon: Package, color: "text-blue-400", label: "Processing" },
  shipped: { icon: Truck, color: "text-cyan-400", label: "Shipped" },
  delivered: { icon: CheckCircle, color: "text-green-400", label: "Delivered" },
  cancelled: { icon: XCircle, color: "text-red-400", label: "Cancelled" },
};

export default function OrderCard({ data }: { data: OrderData }) {
  const status = statusConfig[data.status] ?? statusConfig.pending;
  const StatusIcon = status.icon;

  return (
    <div className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 bg-white/[0.01]">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-cyan-400" />
          <span className="text-sm text-white font-medium">Order</span>
          <span className="text-xs text-neutral-600 font-mono">{data.order_id}</span>
        </div>
        <span className={`flex items-center gap-1 text-xs ${status.color}`}>
          <StatusIcon className="w-3 h-3" />
          {status.label}
        </span>
      </div>
      <div className="p-4">
        <div className="space-y-2">
          {data.items.map((item, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-neutral-300">
                {item.name} <span className="text-neutral-600">x{item.quantity}</span>
              </span>
              <span className="text-neutral-400">{item.price}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
          <span className="text-sm text-neutral-500">Total</span>
          <span className="text-sm text-white font-semibold">{data.total}</span>
        </div>
        {data.estimated_delivery && (
          <div className="flex items-center gap-1 mt-2 text-xs text-neutral-500">
            <Truck className="w-3 h-3" />
            Est. delivery: {data.estimated_delivery}
          </div>
        )}
      </div>
    </div>
  );
}
