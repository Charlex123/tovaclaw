import { HelpCircle, Check, X } from "lucide-react";

interface ConfirmationData {
  title: string;
  message: string;
  details?: Record<string, string>;
  confirm_label?: string;
  cancel_label?: string;
}

export default function ConfirmationCard({ data }: { data: ConfirmationData }) {
  return (
    <div className="mt-2 rounded-xl border border-amber-500/20 bg-amber-500/5 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-amber-500/10">
        <HelpCircle className="w-4 h-4 text-amber-400" />
        <span className="text-sm text-amber-300 font-medium">
          {data.title || "Confirmation Required"}
        </span>
      </div>
      <div className="p-4 space-y-3">
        <div className="text-sm text-neutral-300">{data.message}</div>
        {data.details && (
          <div className="space-y-1.5 p-3 rounded-lg bg-black/20">
            {Object.entries(data.details).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-sm">
                <span className="text-neutral-500">{key}</span>
                <span className="text-neutral-200">{value}</span>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 pt-1">
          <button className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all">
            <Check className="w-3 h-3" />
            {data.confirm_label || "Confirm"}
          </button>
          <button className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-neutral-300 border border-white/10 rounded-lg hover:bg-white/5 transition-all">
            <X className="w-3 h-3" />
            {data.cancel_label || "Cancel"}
          </button>
        </div>
      </div>
    </div>
  );
}
