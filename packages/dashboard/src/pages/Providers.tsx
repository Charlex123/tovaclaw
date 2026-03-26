import { useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle,
  XCircle,
  Server,
  Mail,
  Plane,
  Phone,
  Video,
  MapPin,
  Database,
  Upload,
  Calendar,
  Bell,
  Shield,
  HardDrive,
  ImageIcon,
  Film,
  Music,
} from "lucide-react";
import type { ReactNode } from "react";

interface Provider {
  id: string;
  name: string;
  interface: string;
  description: string;
  icon: ReactNode;
  status: "connected" | "not_configured" | "error";
  implementation?: string;
}

const initialProviders: Provider[] = [
  {
    id: "backend",
    name: "Backend",
    interface: "BaseBackend",
    description: "Domain logic, orders, products, and appointments",
    icon: <Server className="w-5 h-5" />,
    status: "connected",
    implementation: "CustomBackend",
  },
  {
    id: "store",
    name: "Store",
    interface: "BaseStore",
    description: "User profiles, order history, conversations, and search",
    icon: <HardDrive className="w-5 h-5" />,
    status: "connected",
    implementation: "SQLiteStore",
  },
  {
    id: "auth",
    name: "Auth",
    interface: "BaseAuth",
    description: "Token verification and session management",
    icon: <Shield className="w-5 h-5" />,
    status: "connected",
    implementation: "SessionAuth",
  },
  {
    id: "notifier",
    name: "Notifier",
    interface: "BaseNotifier",
    description: "Push notifications, calls, and SMS alerts",
    icon: <Bell className="w-5 h-5" />,
    status: "connected",
    implementation: "BuiltinNotifier",
  },
  {
    id: "email",
    name: "Email",
    interface: "BaseEmailProvider",
    description: "IMAP/SMTP email management with encrypted credentials",
    icon: <Mail className="w-5 h-5" />,
    status: "connected",
    implementation: "ImapEmailProvider",
  },
  {
    id: "travel",
    name: "Travel",
    interface: "BaseTravelProvider",
    description: "Flights, trains, buses, and car hire search",
    icon: <Plane className="w-5 h-5" />,
    status: "connected",
    implementation: "SerpApiTravel",
  },
  {
    id: "calendar",
    name: "Calendar",
    interface: "BaseCalendarProvider",
    description: "Event scheduling and calendar management",
    icon: <Calendar className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "telephony",
    name: "Telephony",
    interface: "BaseTelephony",
    description: "Phone calls and SMS via Twilio integration",
    icon: <Phone className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "video",
    name: "Video Stream",
    interface: "BaseVideoStream",
    description: "CCTV and video feed monitoring with frame analysis",
    icon: <Video className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "geolocation",
    name: "Geolocation",
    interface: "BaseGeolocationProvider",
    description: "Vehicle and fleet GPS tracking with geofencing",
    icon: <MapPin className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "vector_store",
    name: "Vector Store",
    interface: "BaseVectorStore",
    description: "Vector embeddings for RAG with ChromaDB, Pinecone, or Qdrant",
    icon: <Database className="w-5 h-5" />,
    status: "error",
    implementation: "ChromaStore",
  },
  {
    id: "file_store",
    name: "File Store",
    interface: "BaseFileStore",
    description: "File upload, storage, and sharing",
    icon: <Upload className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "image_gen",
    name: "Image Generator",
    interface: "BaseImageGenerator",
    description: "AI image generation from text prompts (DALL-E, Stable Diffusion)",
    icon: <ImageIcon className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "video_gen",
    name: "Video Generator",
    interface: "BaseVideoGenerator",
    description: "AI video generation from text or image inputs",
    icon: <Film className="w-5 h-5" />,
    status: "not_configured",
  },
  {
    id: "audio_gen",
    name: "Audio Generator",
    interface: "BaseAudioGenerator",
    description: "Text-to-speech and audio generation",
    icon: <Music className="w-5 h-5" />,
    status: "not_configured",
  },
];

const statusConfig = {
  connected: {
    label: "Connected",
    color: "text-green-400 bg-green-400/10",
    icon: <CheckCircle className="w-3.5 h-3.5" />,
  },
  not_configured: {
    label: "Not Configured",
    color: "text-neutral-400 bg-neutral-400/10",
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
  error: {
    label: "Error",
    color: "text-red-400 bg-red-400/10",
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
};

export default function Providers() {
  const [providers] = useState<Provider[]>(initialProviders);
  const [filter, setFilter] = useState<"all" | "connected" | "not_configured">(
    "all"
  );

  const filtered =
    filter === "all"
      ? providers
      : providers.filter((p) => p.status === filter);

  const connectedCount = providers.filter(
    (p) => p.status === "connected"
  ).length;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">
          {connectedCount} of {providers.length} providers connected. Implement
          provider interfaces to enable features.
        </p>
        <div className="flex gap-1 p-1 bg-white/[0.02] border border-white/5 rounded-lg">
          {(["all", "connected", "not_configured"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs rounded-md transition-all ${
                filter === f
                  ? "bg-white/10 text-white font-medium"
                  : "text-neutral-500 hover:text-neutral-300"
              }`}
            >
              {f === "all"
                ? "All"
                : f === "connected"
                ? "Connected"
                : "Not Configured"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((provider, i) => {
          const status = statusConfig[provider.status];
          return (
            <motion.div
              key={provider.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="p-5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400">
                  {provider.icon}
                </div>
                <span
                  className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${status.color}`}
                >
                  {status.icon}
                  {status.label}
                </span>
              </div>
              <h3 className="text-white font-medium text-sm">
                {provider.name}
              </h3>
              <div className="font-mono text-xs text-cyan-400/70 mt-0.5">
                {provider.interface}
              </div>
              <p className="text-xs text-neutral-500 mt-2 leading-relaxed">
                {provider.description}
              </p>
              {provider.implementation && (
                <div className="mt-3 pt-3 border-t border-white/5 text-xs text-neutral-600">
                  Implementation:{" "}
                  <span className="text-neutral-400 font-mono">
                    {provider.implementation}
                  </span>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
