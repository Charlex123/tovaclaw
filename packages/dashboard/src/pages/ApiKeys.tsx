import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Key,
  Plus,
  Eye,
  EyeOff,
  Trash2,
  CheckCircle,
  AlertCircle,
  X,
} from "lucide-react";

interface ApiKey {
  id: string;
  provider: string;
  name: string;
  key: string;
  status: "active" | "invalid";
  addedAt: string;
}

const providerOptions = [
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "openai", label: "OpenAI (GPT)" },
  { value: "google", label: "Google (Gemini)" },
  { value: "cohere", label: "Cohere" },
  { value: "custom", label: "Custom Provider" },
];

const initialKeys: ApiKey[] = [
  {
    id: "1",
    provider: "anthropic",
    name: "Anthropic (Claude)",
    key: "sk-ant-api03-****************************",
    status: "active",
    addedAt: "2026-03-20",
  },
  {
    id: "2",
    provider: "openai",
    name: "OpenAI (GPT)",
    key: "sk-proj-****************************",
    status: "active",
    addedAt: "2026-03-18",
  },
  {
    id: "3",
    provider: "google",
    name: "Google (Gemini)",
    key: "AIza****************************",
    status: "invalid",
    addedAt: "2026-03-15",
  },
];

export default function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>(initialKeys);
  const [showModal, setShowModal] = useState(false);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [newKey, setNewKey] = useState({ provider: "anthropic", key: "" });

  const toggleVisibility = (id: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const deleteKey = (id: string) => {
    setKeys((prev) => prev.filter((k) => k.id !== id));
  };

  const addKey = () => {
    if (!newKey.key.trim()) return;
    const provider = providerOptions.find((p) => p.value === newKey.provider);
    const key: ApiKey = {
      id: Date.now().toString(),
      provider: newKey.provider,
      name: provider?.label ?? newKey.provider,
      key: newKey.key.slice(0, 8) + "****************************",
      status: "active",
      addedAt: new Date().toISOString().split("T")[0],
    };
    setKeys((prev) => [...prev, key]);
    setNewKey({ provider: "anthropic", key: "" });
    setShowModal(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-neutral-500 mt-1">
            Manage API keys for LLM providers. Keys are encrypted at rest.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Add Key
        </button>
      </div>

      <div className="space-y-3">
        {keys.map((apiKey, i) => (
          <motion.div
            key={apiKey.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="p-5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Key className="w-4.5 h-4.5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">
                      {apiKey.name}
                    </span>
                    {apiKey.status === "active" ? (
                      <span className="flex items-center gap-1 text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
                        <CheckCircle className="w-3 h-3" />
                        Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
                        <AlertCircle className="w-3 h-3" />
                        Invalid
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-neutral-500 mt-1 font-mono">
                    {visibleKeys.has(apiKey.id)
                      ? apiKey.key
                      : "••••••••••••••••••••••••••••••"}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-600 mr-2">
                  Added {apiKey.addedAt}
                </span>
                <button
                  onClick={() => toggleVisibility(apiKey.id)}
                  className="p-2 text-neutral-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                >
                  {visibleKeys.has(apiKey.id) ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={() => deleteKey(apiKey.id)}
                  className="p-2 text-neutral-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {keys.length === 0 && (
        <div className="text-center py-16">
          <Key className="w-10 h-10 text-neutral-600 mx-auto mb-3" />
          <p className="text-neutral-500">No API keys configured</p>
          <p className="text-sm text-neutral-600 mt-1">
            Add a key to start using LLM providers
          </p>
        </div>
      )}

      {/* Add Key Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md p-6 rounded-2xl border border-white/10 bg-[#141414]"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-white">
                  Add API Key
                </h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1 text-neutral-500 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Provider
                  </label>
                  <select
                    value={newKey.provider}
                    onChange={(e) =>
                      setNewKey((prev) => ({
                        ...prev,
                        provider: e.target.value,
                      }))
                    }
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                  >
                    {providerOptions.map((opt) => (
                      <option
                        key={opt.value}
                        value={opt.value}
                        className="bg-[#1a1a1a]"
                      >
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={newKey.key}
                    onChange={(e) =>
                      setNewKey((prev) => ({ ...prev, key: e.target.value }))
                    }
                    placeholder="sk-..."
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
                  />
                </div>

                <button
                  onClick={addKey}
                  className="w-full py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all mt-2"
                >
                  Add API Key
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
