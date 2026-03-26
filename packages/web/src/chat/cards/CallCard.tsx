import { Phone, PhoneCall } from "lucide-react";
import { useChatActions } from "../ChatContext";

interface CallData {
  call_id: string;
  to: string;
  status: "ringing" | "in_progress" | "completed" | "failed";
  type: string;
  started_at: string;
  via: string;
}

const statusStyles: Record<string, string> = {
  ringing: "text-amber-400 bg-amber-400/10",
  in_progress: "text-green-400 bg-green-400/10",
  completed: "text-neutral-400 bg-neutral-400/10",
  failed: "text-red-400 bg-red-400/10",
};

export default function CallCard({ data }: { data: CallData }) {
  const { sendMessage } = useChatActions();

  return (
    <div className="mt-3 p-4 rounded-lg bg-white/[0.03] border border-white/5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center">
          <PhoneCall className="w-5 h-5 text-green-400" />
        </div>
        <div>
          <div className="text-sm text-white font-mono">{data.to}</div>
          <div className="text-[10px] text-neutral-500">
            {data.type} call via {data.via}
          </div>
        </div>
        <span
          className={`ml-auto text-[10px] px-2 py-0.5 rounded-full ${statusStyles[data.status]}`}
        >
          {data.status.replace("_", " ")}
        </span>
      </div>
      <div className="flex items-center gap-4 text-[10px] text-neutral-600">
        <span>ID: {data.call_id}</span>
        <span>Started: {data.started_at}</span>
      </div>
      {(data.status === "ringing" || data.status === "in_progress") && (
        <div className="flex gap-2 mt-3">
          <button
            onClick={() => sendMessage("End call")}
            className="flex-1 py-1.5 text-xs text-red-400 border border-red-400/20 rounded-lg hover:bg-red-400/10 transition-colors flex items-center justify-center gap-1"
          >
            <Phone className="w-3 h-3" />
            End Call
          </button>
        </div>
      )}
    </div>
  );
}
