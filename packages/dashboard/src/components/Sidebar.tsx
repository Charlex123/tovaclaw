import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Key,
  Database,
  Bot,
  Plug,
  Wrench,
  Brain,
  Settings,
  ExternalLink,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/agents", icon: Bot, label: "Agents" },
  { to: "/providers", icon: Plug, label: "Providers" },
  { to: "/tools", icon: Wrench, label: "Tools" },
  { to: "/brain-box", icon: Brain, label: "Brain Box" },
  { to: "/api-keys", icon: Key, label: "API Keys" },
  { to: "/database", icon: Database, label: "Database" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 bg-[#111111] border-r border-white/5 flex flex-col z-40">
      <div className="h-16 flex items-center gap-2 px-6 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center font-bold text-white text-sm">
          T
        </div>
        <span className="text-lg font-semibold text-white tracking-tight">
          TovaClaw
        </span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                isActive
                  ? "bg-white/10 text-white font-medium"
                  : "text-neutral-400 hover:text-white hover:bg-white/5"
              }`
            }
          >
            <item.icon className="w-4.5 h-4.5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 pb-4">
        <a
          href="https://github.com/charlex123/tovaclaw"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-neutral-500 hover:text-neutral-300 hover:bg-white/5 transition-all"
        >
          <ExternalLink className="w-4 h-4" />
          Documentation
        </a>
      </div>
    </aside>
  );
}
