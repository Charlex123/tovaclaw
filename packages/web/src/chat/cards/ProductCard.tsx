import { ShoppingCart } from "lucide-react";
import { useChatActions } from "../ChatContext";

interface Product {
  id: string;
  name: string;
  price: string;
  image?: string;
  category?: string;
  in_stock: boolean;
}

export default function ProductCard({ data }: { data: { results: Product[] } }) {
  const { sendMessage } = useChatActions();
  const products = data.results ?? [];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
      {products.map((p) => (
        <div
          key={p.id}
          className="flex items-center gap-3 p-3 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
        >
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500/10 to-pink-500/10 flex items-center justify-center text-purple-400 shrink-0 text-xs font-bold">
            {p.image ? (
              <img src={p.image} alt={p.name} className="w-full h-full rounded-lg object-cover" />
            ) : (
              p.name.slice(0, 2).toUpperCase()
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-white font-medium truncate">{p.name}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-sm text-cyan-400 font-semibold">{p.price}</span>
              {p.category && (
                <span className="text-xs text-neutral-600">{p.category}</span>
              )}
              {!p.in_stock && (
                <span className="text-xs text-red-400">Out of stock</span>
              )}
            </div>
          </div>
          <button
            onClick={() => sendMessage(`Add to cart: ${p.name} (${p.price})`)}
            disabled={!p.in_stock}
            className="p-2 rounded-lg text-cyan-400 hover:bg-cyan-400/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ShoppingCart className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
