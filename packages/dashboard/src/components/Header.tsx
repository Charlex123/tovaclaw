import { useLocation } from "react-router-dom";
import { Bell, Search } from "lucide-react";

const pageTitles: Record<string, string> = {
  "/": "Overview",
  "/agents": "Agents",
  "/providers": "Providers",
  "/tools": "Tools",
  "/brain-box": "Brain Box",
  "/api-keys": "API Keys",
  "/database": "Database",
  "/settings": "Settings",
};

export default function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? "Dashboard";

  return (
    <header className="fixed top-0 right-0 left-64 h-16 bg-[#0a0a0a]/80 backdrop-blur-xl border-b border-white/5 flex items-center justify-between px-6 z-30">
      <h1 className="text-lg font-semibold text-white">{title}</h1>

      <div className="flex items-center gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search..."
            className="w-64 pl-9 pr-4 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-neutral-300 placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 focus:bg-white/[0.07] transition-all"
          />
        </div>
        <button className="relative p-2 text-neutral-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
          <Bell className="w-4.5 h-4.5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full" />
        </button>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-bold">
          A
        </div>
      </div>
    </header>
  );
}
