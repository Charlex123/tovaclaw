import { AlertTriangle, Siren, CheckCircle } from "lucide-react";
import { useChatActions } from "../ChatContext";

interface EmergencyData {
  id: string;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  location?: string;
  reported_at: string;
  status: "active" | "acknowledged" | "resolved";
}

const severityColors = {
  low: "border-green-500/30 bg-green-500/5",
  medium: "border-amber-500/30 bg-amber-500/5",
  high: "border-orange-500/30 bg-orange-500/5",
  critical: "border-red-500/30 bg-red-500/5",
};

const severityText = {
  low: "text-green-400",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export default function EmergencyCard({ data }: { data: EmergencyData }) {
  const { sendMessage } = useChatActions();

  return (
    <div
      className={`mt-2 rounded-xl border-2 overflow-hidden ${
        severityColors[data.severity]
      }`}
    >
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5">
        {data.severity === "critical" ? (
          <Siren className={`w-4 h-4 ${severityText[data.severity]}`} />
        ) : (
          <AlertTriangle className={`w-4 h-4 ${severityText[data.severity]}`} />
        )}
        <span className={`text-sm font-semibold ${severityText[data.severity]}`}>
          {data.severity.toUpperCase()} - {data.type}
        </span>
        <span className="text-xs text-neutral-600 ml-auto font-mono">{data.id}</span>
      </div>
      <div className="p-4 space-y-2">
        <div className="text-sm text-neutral-200">{data.description}</div>
        <div className="flex flex-wrap gap-3 text-xs text-neutral-500">
          {data.location && <span>Location: {data.location}</span>}
          <span>Reported: {data.reported_at}</span>
          <span className="flex items-center gap-1">
            {data.status === "resolved" ? (
              <CheckCircle className="w-3 h-3 text-green-400" />
            ) : (
              <AlertTriangle className="w-3 h-3" />
            )}
            {data.status}
          </span>
        </div>
        {data.status === "active" && (
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => sendMessage(`Acknowledge emergency ${data.id}`)}
              className="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-500 transition-colors"
            >
              Acknowledge
            </button>
            <button
              onClick={() => sendMessage(`Escalate emergency ${data.id} to critical`)}
              className="px-3 py-1.5 text-xs font-medium text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/10 transition-colors"
            >
              Escalate
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
