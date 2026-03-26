import { useState } from "react";
import { motion } from "framer-motion";
import {
  Database as DatabaseIcon,
  CheckCircle,
  Circle,
  Server,
  TestTube,
  Loader2,
} from "lucide-react";

interface DatabaseOption {
  id: string;
  name: string;
  description: string;
  icon: string;
}

const databases: DatabaseOption[] = [
  {
    id: "postgresql",
    name: "PostgreSQL",
    description: "Robust relational database with full SQL support",
    icon: "PG",
  },
  {
    id: "firebase",
    name: "Firebase Firestore",
    description: "NoSQL cloud database by Google with realtime sync",
    icon: "FB",
  },
  {
    id: "mongodb",
    name: "MongoDB",
    description: "Document-oriented NoSQL database for flexible schemas",
    icon: "MG",
  },
  {
    id: "sqlite",
    name: "SQLite",
    description: "Lightweight embedded database, great for development",
    icon: "SL",
  },
  {
    id: "redis",
    name: "Redis",
    description: "In-memory store for caching and session management",
    icon: "RD",
  },
  {
    id: "supabase",
    name: "Supabase",
    description: "Open-source Firebase alternative built on PostgreSQL",
    icon: "SB",
  },
];

export default function Database() {
  const [selected, setSelected] = useState("postgresql");
  const [connectionString, setConnectionString] = useState(
    "postgresql://user:****@localhost:5432/tovaclaw"
  );
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "error" | null>(
    null
  );

  const testConnection = () => {
    setTesting(true);
    setTestResult(null);
    setTimeout(() => {
      setTesting(false);
      setTestResult("success");
    }, 1500);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <p className="text-sm text-neutral-500">
        Select and configure the database backend for storing conversations,
        agent state, and user data.
      </p>

      {/* Database Selection */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {databases.map((db, i) => (
          <motion.button
            key={db.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            onClick={() => {
              setSelected(db.id);
              setTestResult(null);
            }}
            className={`relative p-4 rounded-xl border text-left transition-all ${
              selected === db.id
                ? "border-blue-500/50 bg-blue-500/5"
                : "border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10"
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400 text-xs font-bold font-mono">
                {db.icon}
              </div>
              {selected === db.id ? (
                <CheckCircle className="w-5 h-5 text-blue-400" />
              ) : (
                <Circle className="w-5 h-5 text-neutral-700" />
              )}
            </div>
            <h3 className="text-white font-medium text-sm">{db.name}</h3>
            <p className="text-xs text-neutral-500 mt-1">{db.description}</p>
          </motion.button>
        ))}
      </div>

      {/* Connection Configuration */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02] space-y-4"
      >
        <div className="flex items-center gap-2 mb-2">
          <Server className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Connection Settings</h2>
        </div>

        <div>
          <label className="block text-sm text-neutral-400 mb-2">
            Connection String
          </label>
          <input
            type="text"
            value={connectionString}
            onChange={(e) => setConnectionString(e.target.value)}
            placeholder="postgresql://user:password@host:port/database"
            className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Pool Size
            </label>
            <input
              type="number"
              defaultValue={10}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Timeout (ms)
            </label>
            <input
              type="number"
              defaultValue={5000}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={testConnection}
            disabled={testing}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white border border-white/10 rounded-lg hover:bg-white/5 transition-all disabled:opacity-50"
          >
            {testing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <TestTube className="w-4 h-4" />
            )}
            Test Connection
          </button>
          <button className="px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all">
            Save Configuration
          </button>
          {testResult === "success" && (
            <span className="flex items-center gap-1 text-sm text-green-400">
              <CheckCircle className="w-4 h-4" />
              Connection successful
            </span>
          )}
        </div>
      </motion.div>

      {/* Current Status */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="p-5 rounded-xl border border-white/5 bg-white/[0.02] flex items-center gap-4"
      >
        <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
          <DatabaseIcon className="w-5 h-5 text-green-400" />
        </div>
        <div>
          <div className="text-sm text-white font-medium">
            Currently connected to PostgreSQL
          </div>
          <div className="text-xs text-neutral-500 font-mono mt-0.5">
            localhost:5432/tovaclaw &middot; Pool: 10 &middot; Latency: 2ms
          </div>
        </div>
        <span className="ml-auto text-xs text-green-400 bg-green-400/10 px-2.5 py-1 rounded-full">
          Connected
        </span>
      </motion.div>
    </div>
  );
}
