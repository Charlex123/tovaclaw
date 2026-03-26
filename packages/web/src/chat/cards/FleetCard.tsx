import { Car, MapPin, Battery, AlertTriangle } from "lucide-react";

interface Vehicle {
  id: string;
  plate: string;
  driver: string;
  speed: string;
  status: "moving" | "parked" | "speeding";
  location: string;
  battery: string;
}

const statusStyles: Record<string, string> = {
  moving: "text-green-400 bg-green-400/10",
  parked: "text-neutral-400 bg-neutral-400/10",
  speeding: "text-red-400 bg-red-400/10",
};

export default function FleetCard({
  data,
}: {
  data: { vehicles: Vehicle[] };
}) {
  return (
    <div className="mt-3 space-y-2">
      {data.vehicles.map((v) => (
        <div
          key={v.id}
          className="p-3 rounded-lg bg-white/[0.03] border border-white/5"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Car className="w-4 h-4 text-cyan-400" />
              <span className="text-sm text-white font-mono">{v.plate}</span>
              <span className="text-xs text-neutral-500">{v.driver}</span>
            </div>
            <span
              className={`flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${statusStyles[v.status]}`}
            >
              {v.status === "speeding" && (
                <AlertTriangle className="w-3 h-3" />
              )}
              {v.status}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-2 text-[10px] text-neutral-500">
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {v.location}
            </span>
            <span>{v.speed}</span>
            <span className="flex items-center gap-1">
              <Battery className="w-3 h-3" />
              {v.battery}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
