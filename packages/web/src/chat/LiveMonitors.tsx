import { useState } from "react";
import {
  Video,
  MapPin,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Circle,
} from "lucide-react";

interface CameraFeed {
  id: string;
  name: string;
  status: "online" | "offline";
  lastAnomaly?: string;
}

interface VehiclePosition {
  id: string;
  name: string;
  lat: number;
  lng: number;
  speed: number;
  status: "moving" | "idle" | "alert";
}

interface EmergencyItem {
  id: string;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  time: string;
}

const mockCameras: CameraFeed[] = [
  { id: "cam1", name: "Main Entrance", status: "online" },
  { id: "cam2", name: "Parking Lot A", status: "online", lastAnomaly: "2 min ago" },
  { id: "cam3", name: "Loading Bay", status: "offline" },
  { id: "cam4", name: "Server Room", status: "online" },
];

const mockVehicles: VehiclePosition[] = [
  { id: "v1", name: "Truck-001", lat: 6.45, lng: 3.39, speed: 45, status: "moving" },
  { id: "v2", name: "Van-003", lat: 6.52, lng: 3.38, speed: 0, status: "idle" },
  { id: "v3", name: "Bike-012", lat: 6.48, lng: 3.41, speed: 22, status: "alert" },
];

const mockEmergencies: EmergencyItem[] = [
  { id: "e1", type: "Motion detected", severity: "medium", time: "2m ago" },
  { id: "e2", type: "Geofence breach", severity: "high", time: "15m ago" },
];

const severityDot = {
  low: "text-green-400",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

const vehicleStatusColor = {
  moving: "text-green-400",
  idle: "text-neutral-500",
  alert: "text-red-400",
};

export default function LiveMonitors() {
  const [expanded, setExpanded] = useState(false);

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center justify-center gap-2 px-4 py-2 border-t border-white/5 bg-[#0a0a0a] text-xs text-neutral-500 hover:text-neutral-300 transition-colors w-full"
      >
        <ChevronUp className="w-3 h-3" />
        Live Monitors
        {mockEmergencies.length > 0 && (
          <span className="flex items-center gap-1 text-amber-400">
            <Circle className="w-2 h-2 fill-current" />
            {mockEmergencies.length}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="border-t border-white/5 bg-[#0a0a0a]">
      <button
        onClick={() => setExpanded(false)}
        className="flex items-center justify-center gap-2 px-4 py-2 text-xs text-neutral-500 hover:text-neutral-300 transition-colors w-full border-b border-white/5"
      >
        <ChevronDown className="w-3 h-3" />
        Hide Monitors
      </button>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/5">
        {/* CCTV Feeds */}
        <div className="bg-[#0a0a0a] p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-neutral-400 mb-2">
            <Video className="w-3 h-3 text-cyan-400" />
            CCTV Feeds
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {mockCameras.map((cam) => (
              <div
                key={cam.id}
                className="p-2 rounded-lg bg-white/[0.02] border border-white/5"
              >
                <div className="flex items-center gap-1 mb-1">
                  <Circle
                    className={`w-2 h-2 fill-current ${
                      cam.status === "online" ? "text-green-400" : "text-red-400"
                    }`}
                  />
                  <span className="text-[10px] text-neutral-400 truncate">
                    {cam.name}
                  </span>
                </div>
                <div className="h-10 rounded bg-black/40 flex items-center justify-center">
                  <Video className="w-3 h-3 text-neutral-700" />
                </div>
                {cam.lastAnomaly && (
                  <div className="text-[9px] text-amber-400/60 mt-1">
                    Anomaly: {cam.lastAnomaly}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Fleet GPS */}
        <div className="bg-[#0a0a0a] p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-neutral-400 mb-2">
            <MapPin className="w-3 h-3 text-cyan-400" />
            Fleet Tracking
          </div>
          <div className="space-y-1.5">
            {mockVehicles.map((v) => (
              <div
                key={v.id}
                className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/5"
              >
                <Circle
                  className={`w-2 h-2 fill-current shrink-0 ${
                    vehicleStatusColor[v.status]
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-neutral-300 truncate">
                    {v.name}
                  </div>
                  <div className="text-[9px] text-neutral-600">
                    {v.speed} km/h &middot; {v.lat.toFixed(2)}, {v.lng.toFixed(2)}
                  </div>
                </div>
                <span className={`text-[9px] ${vehicleStatusColor[v.status]}`}>
                  {v.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Emergency Ticker */}
        <div className="bg-[#0a0a0a] p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-neutral-400 mb-2">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            Alerts
          </div>
          <div className="space-y-1.5">
            {mockEmergencies.map((e) => (
              <div
                key={e.id}
                className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/5"
              >
                <Circle
                  className={`w-2 h-2 fill-current shrink-0 ${
                    severityDot[e.severity]
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-neutral-300">{e.type}</div>
                  <div className="text-[9px] text-neutral-600">
                    {e.severity} &middot; {e.time}
                  </div>
                </div>
              </div>
            ))}
            {mockEmergencies.length === 0 && (
              <div className="text-[10px] text-neutral-700 text-center py-4">
                No active alerts
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
