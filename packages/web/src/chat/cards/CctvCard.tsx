import { Video, Wifi, WifiOff } from "lucide-react";

interface Camera {
  id: string;
  name: string;
  status: "online" | "offline";
  lastEvent: string;
  fps: number;
}

export default function CctvCard({ data }: { data: { cameras: Camera[] } }) {
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      {data.cameras.map((cam) => (
        <div
          key={cam.id}
          className="p-3 rounded-lg bg-white/[0.03] border border-white/5"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Video className="w-4 h-4 text-cyan-400" />
              <span className="text-xs text-white font-medium">
                {cam.name}
              </span>
            </div>
            {cam.status === "online" ? (
              <Wifi className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
            )}
          </div>
          <div className="text-[10px] text-neutral-500">{cam.lastEvent}</div>
          {cam.status === "online" && (
            <div className="text-[10px] text-neutral-600 mt-1">
              {cam.fps} FPS
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
