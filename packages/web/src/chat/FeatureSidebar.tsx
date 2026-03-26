import { Link } from "react-router-dom";
import {
  MessageSquare,
  Mail,
  Plane,
  CheckSquare,
  FileText,
  Calendar,
  ShoppingCart,
  AlertTriangle,
  Video,
  Car,
  Phone,
  Globe,
  Plus,
  ArrowLeft,
} from "lucide-react";
import type { ReactNode } from "react";

interface FeatureItem {
  id: string;
  label: string;
  icon: ReactNode;
  color: string;
}

const features: FeatureItem[] = [
  { id: "chat", label: "Chat", icon: <MessageSquare className="w-4.5 h-4.5" />, color: "text-cyan-400" },
  { id: "email", label: "Email", icon: <Mail className="w-4.5 h-4.5" />, color: "text-blue-400" },
  { id: "travel", label: "Travel", icon: <Plane className="w-4.5 h-4.5" />, color: "text-sky-400" },
  { id: "orders", label: "Orders", icon: <ShoppingCart className="w-4.5 h-4.5" />, color: "text-purple-400" },
  { id: "todos", label: "Todos", icon: <CheckSquare className="w-4.5 h-4.5" />, color: "text-green-400" },
  { id: "notes", label: "Notes", icon: <FileText className="w-4.5 h-4.5" />, color: "text-amber-400" },
  { id: "events", label: "Events", icon: <Calendar className="w-4.5 h-4.5" />, color: "text-pink-400" },
  { id: "emergency", label: "Emergency", icon: <AlertTriangle className="w-4.5 h-4.5" />, color: "text-red-400" },
  { id: "cctv", label: "CCTV", icon: <Video className="w-4.5 h-4.5" />, color: "text-indigo-400" },
  { id: "fleet", label: "Fleet", icon: <Car className="w-4.5 h-4.5" />, color: "text-teal-400" },
  { id: "phone", label: "Phone", icon: <Phone className="w-4.5 h-4.5" />, color: "text-orange-400" },
  { id: "search", label: "Web", icon: <Globe className="w-4.5 h-4.5" />, color: "text-violet-400" },
];

interface FeatureSidebarProps {
  activeFeature: string;
  onSelectFeature: (id: string) => void;
  onNewConversation: () => void;
}

export default function FeatureSidebar({ activeFeature, onSelectFeature, onNewConversation }: FeatureSidebarProps) {
  return (
    <aside className="w-16 bg-[#0a0a0a] border-r border-white/5 flex flex-col items-center py-3 shrink-0">
      {/* Logo / Back */}
      <Link
        to="/"
        className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white mb-4 hover:scale-105 transition-transform"
        title="Back to home"
      >
        <ArrowLeft className="w-4 h-4" />
      </Link>

      {/* Feature icons */}
      <div className="flex-1 space-y-1 overflow-y-auto">
        {features.map((f) => (
          <button
            key={f.id}
            onClick={() => onSelectFeature(f.id)}
            title={f.label}
            className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
              activeFeature === f.id
                ? `${f.color} bg-white/10`
                : "text-neutral-600 hover:text-neutral-300 hover:bg-white/5"
            }`}
          >
            {f.icon}
          </button>
        ))}
      </div>

      {/* New conversation */}
      <button
        onClick={onNewConversation}
        title="New conversation"
        className="w-10 h-10 rounded-xl flex items-center justify-center text-neutral-600 hover:text-cyan-400 hover:bg-white/5 transition-all mt-2"
      >
        <Plus className="w-4.5 h-4.5" />
      </button>
    </aside>
  );
}
