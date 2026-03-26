import { useState } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Mail,
  CheckSquare,
  Calendar,
  Video,
  AlertTriangle,
  Car,
  FileText,
  Clock,
  Trash2,
  Search,
} from "lucide-react";
import type { ReactNode } from "react";

interface MemoryNamespace {
  id: string;
  feature: string;
  icon: ReactNode;
  memoryCount: number;
  lastUpdated: string;
}

interface MemoryEntry {
  id: string;
  key: string;
  value: string;
  category: "user" | "preference" | "fact" | "context" | "history";
  feature: string;
  ttl?: number;
  createdAt: string;
}

const namespaces: MemoryNamespace[] = [
  {
    id: "email",
    feature: "Email",
    icon: <Mail className="w-4 h-4" />,
    memoryCount: 12,
    lastUpdated: "5 min ago",
  },
  {
    id: "todos",
    feature: "Todos",
    icon: <CheckSquare className="w-4 h-4" />,
    memoryCount: 8,
    lastUpdated: "1 hr ago",
  },
  {
    id: "calendar",
    feature: "Calendar",
    icon: <Calendar className="w-4 h-4" />,
    memoryCount: 5,
    lastUpdated: "3 hrs ago",
  },
  {
    id: "cctv",
    feature: "CCTV",
    icon: <Video className="w-4 h-4" />,
    memoryCount: 3,
    lastUpdated: "6 hrs ago",
  },
  {
    id: "emergency",
    feature: "Emergency",
    icon: <AlertTriangle className="w-4 h-4" />,
    memoryCount: 2,
    lastUpdated: "1 day ago",
  },
  {
    id: "vehicle",
    feature: "Vehicle",
    icon: <Car className="w-4 h-4" />,
    memoryCount: 6,
    lastUpdated: "2 hrs ago",
  },
  {
    id: "notes",
    feature: "Notes",
    icon: <FileText className="w-4 h-4" />,
    memoryCount: 15,
    lastUpdated: "30 min ago",
  },
];

const sampleMemories: MemoryEntry[] = [
  {
    id: "1",
    key: "preferred_tone",
    value: "Professional and concise",
    category: "preference",
    feature: "email",
    createdAt: "2026-03-25",
  },
  {
    id: "2",
    key: "signature_style",
    value: "Best regards, followed by full name",
    category: "preference",
    feature: "email",
    createdAt: "2026-03-24",
  },
  {
    id: "3",
    key: "timezone",
    value: "Africa/Lagos (WAT, UTC+1)",
    category: "fact",
    feature: "email",
    ttl: 2592000,
    createdAt: "2026-03-20",
  },
  {
    id: "4",
    key: "auto_categorize",
    value: "Enabled — sort into Work, Personal, Newsletters",
    category: "preference",
    feature: "email",
    createdAt: "2026-03-22",
  },
  {
    id: "5",
    key: "important_contacts",
    value: "team@company.com, cto@company.com (always prioritize)",
    category: "context",
    feature: "email",
    createdAt: "2026-03-23",
  },
];

const categoryColors: Record<string, string> = {
  user: "text-blue-400 bg-blue-400/10",
  preference: "text-purple-400 bg-purple-400/10",
  fact: "text-cyan-400 bg-cyan-400/10",
  context: "text-amber-400 bg-amber-400/10",
  history: "text-green-400 bg-green-400/10",
};

export default function BrainBox() {
  const [selectedNamespace, setSelectedNamespace] = useState("email");
  const [memories, setMemories] = useState<MemoryEntry[]>(sampleMemories);
  const [search, setSearch] = useState("");

  const totalMemories = namespaces.reduce(
    (sum, ns) => sum + ns.memoryCount,
    0
  );

  const filteredMemories = memories.filter(
    (m) =>
      m.feature === selectedNamespace &&
      (search === "" ||
        m.key.includes(search.toLowerCase()) ||
        m.value.toLowerCase().includes(search.toLowerCase()))
  );

  const deleteMemory = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">
          {totalMemories} memories across {namespaces.length} feature namespaces.
          Per-user, isolated memory spaces with optional TTL.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Namespace sidebar */}
        <div className="space-y-2">
          {namespaces.map((ns, i) => (
            <motion.button
              key={ns.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              onClick={() => setSelectedNamespace(ns.id)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
                selectedNamespace === ns.id
                  ? "bg-blue-500/10 border border-blue-500/20 text-white"
                  : "border border-white/5 bg-white/[0.02] text-neutral-400 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  selectedNamespace === ns.id
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-white/5 text-neutral-500"
                }`}
              >
                {ns.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{ns.feature}</div>
                <div className="text-xs text-neutral-600">
                  {ns.memoryCount} memories
                </div>
              </div>
            </motion.button>
          ))}
        </div>

        {/* Memory entries */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search memories..."
                className="w-full pl-9 pr-4 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-neutral-300 placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-all"
              />
            </div>
            <div className="flex items-center gap-1.5 text-xs text-neutral-500">
              <Brain className="w-3.5 h-3.5" />
              {namespaces.find((n) => n.id === selectedNamespace)?.feature}{" "}
              namespace
            </div>
          </div>

          <div className="space-y-2">
            {filteredMemories.map((memory, i) => (
              <motion.div
                key={memory.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="text-sm font-mono text-cyan-400">
                        {memory.key}
                      </code>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          categoryColors[memory.category]
                        }`}
                      >
                        {memory.category}
                      </span>
                      {memory.ttl && (
                        <span className="flex items-center gap-1 text-xs text-amber-400/60">
                          <Clock className="w-3 h-3" />
                          TTL: {Math.round(memory.ttl / 86400)}d
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-neutral-300">{memory.value}</p>
                    <div className="text-xs text-neutral-600 mt-2">
                      Created {memory.createdAt}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteMemory(memory.id)}
                    className="p-1.5 text-neutral-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </motion.div>
            ))}

            {filteredMemories.length === 0 && (
              <div className="text-center py-12">
                <Brain className="w-10 h-10 text-neutral-600 mx-auto mb-3" />
                <p className="text-neutral-500">No memories in this namespace</p>
                <p className="text-sm text-neutral-600 mt-1">
                  Memories are created as agents interact with users
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
