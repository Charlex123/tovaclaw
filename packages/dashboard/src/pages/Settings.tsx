import { useState } from "react";
import { motion } from "framer-motion";
import {
  Globe,
  Shield,
  Bell,
  Palette,
  Save,
  RotateCcw,
  Database,
  Brain,
  Video,
  Phone,
  MapPin,
  GraduationCap,
  Cpu,
} from "lucide-react";

interface ToggleProps {
  label: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}

function Toggle({ label, description, enabled, onToggle }: ToggleProps) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <div className="text-sm text-white">{label}</div>
        <div className="text-xs text-neutral-500 mt-0.5">{description}</div>
      </div>
      <button
        onClick={onToggle}
        className={`relative w-11 h-6 rounded-full transition-colors ${
          enabled ? "bg-blue-500" : "bg-neutral-700"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
            enabled ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState({
    streamingEnabled: true,
    debugMode: false,
    autoRestart: true,
    notifications: true,
    analyticsEnabled: false,
    corsOrigin: "*",
    maxTokens: "4096",
    temperature: "0.3",
    maxIterations: "15",
    rateLimitRpm: "60",
    llmProvider: "anthropic",
    authMode: "session",
    embeddingsProvider: "openai",
    vectorStore: "chromadb",
    chunkSize: "512",
    chunkOverlap: "50",
    twilioEnabled: false,
    videoAnalysisInterval: "30",
    gpsPollInterval: "60",
    emergencyCheckInterval: "15",
    brainBoxEnabled: true,
    learningEnabled: true,
    standaloneMode: false,
    ossModelId: "",
    reasoningModelId: "",
    thinkingTokens: true,
    visionModel: "",
    vramAware: true,
    dataCollection: true,
    trainingAutoRetrain: false,
    trainingMinSamples: "100",
  });

  const toggle = (key: keyof typeof settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const updateField = (key: keyof typeof settings, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <p className="text-sm text-neutral-500">
        Configure global settings for your TovaClaw instance. Maps to
        TovaSettings in tova_core/config.py.
      </p>

      {/* General */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">General</h2>
        </div>
        <div className="divide-y divide-white/5">
          <Toggle
            label="Streaming Responses"
            description="Stream LLM responses token-by-token to clients"
            enabled={settings.streamingEnabled as boolean}
            onToggle={() => toggle("streamingEnabled")}
          />
          <Toggle
            label="Debug Mode"
            description="Enable verbose logging for all agent interactions"
            enabled={settings.debugMode as boolean}
            onToggle={() => toggle("debugMode")}
          />
          <Toggle
            label="Auto-Restart Agents"
            description="Automatically restart agents after crashes"
            enabled={settings.autoRestart as boolean}
            onToggle={() => toggle("autoRestart")}
          />
          <Toggle
            label="Standalone Mode"
            description="Zero-config with SQLite, session auth, and all built-in features"
            enabled={settings.standaloneMode as boolean}
            onToggle={() => toggle("standaloneMode")}
          />
        </div>
      </motion.div>

      {/* LLM Defaults */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Palette className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">LLM Defaults</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Default Provider
            </label>
            <select
              value={settings.llmProvider}
              onChange={(e) => updateField("llmProvider", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            >
              <option value="anthropic" className="bg-[#1a1a1a]">
                Anthropic (Claude)
              </option>
              <option value="openai" className="bg-[#1a1a1a]">
                OpenAI (GPT)
              </option>
              <option value="google" className="bg-[#1a1a1a]">
                Google (Gemini)
              </option>
              <option value="local" className="bg-[#1a1a1a]">
                Local (Ollama / vLLM)
              </option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Auth Mode
            </label>
            <select
              value={settings.authMode}
              onChange={(e) => updateField("authMode", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            >
              <option value="session" className="bg-[#1a1a1a]">
                Session
              </option>
              <option value="jwt" className="bg-[#1a1a1a]">
                JWT
              </option>
              <option value="apikey" className="bg-[#1a1a1a]">
                API Key
              </option>
              <option value="none" className="bg-[#1a1a1a]">
                None
              </option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Max Tokens
            </label>
            <input
              type="number"
              value={settings.maxTokens}
              onChange={(e) => updateField("maxTokens", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Temperature
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={settings.temperature}
              onChange={(e) => updateField("temperature", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Max Iterations
            </label>
            <input
              type="number"
              value={settings.maxIterations}
              onChange={(e) => updateField("maxIterations", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* RAG & Embeddings */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Database className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">RAG & Embeddings</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Embeddings Provider
            </label>
            <select
              value={settings.embeddingsProvider}
              onChange={(e) =>
                updateField("embeddingsProvider", e.target.value)
              }
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            >
              <option value="openai" className="bg-[#1a1a1a]">
                OpenAI
              </option>
              <option value="google" className="bg-[#1a1a1a]">
                Google
              </option>
              <option value="cohere" className="bg-[#1a1a1a]">
                Cohere
              </option>
              <option value="local" className="bg-[#1a1a1a]">
                Local
              </option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Vector Store
            </label>
            <select
              value={settings.vectorStore}
              onChange={(e) => updateField("vectorStore", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            >
              <option value="chromadb" className="bg-[#1a1a1a]">
                ChromaDB
              </option>
              <option value="pinecone" className="bg-[#1a1a1a]">
                Pinecone
              </option>
              <option value="qdrant" className="bg-[#1a1a1a]">
                Qdrant
              </option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Chunk Size
            </label>
            <input
              type="number"
              value={settings.chunkSize}
              onChange={(e) => updateField("chunkSize", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Chunk Overlap
            </label>
            <input
              type="number"
              value={settings.chunkOverlap}
              onChange={(e) => updateField("chunkOverlap", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* Brain Box & Learning */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Memory & Learning</h2>
        </div>
        <div className="divide-y divide-white/5">
          <Toggle
            label="Brain Box Memory"
            description="Per-feature, per-user memory namespaces with TTL support"
            enabled={settings.brainBoxEnabled as boolean}
            onToggle={() => toggle("brainBoxEnabled")}
          />
          <Toggle
            label="Self-Learning Engine"
            description="Continuous improvement from agent interactions"
            enabled={settings.learningEnabled as boolean}
            onToggle={() => toggle("learningEnabled")}
          />
        </div>
      </motion.div>

      {/* Training & OSS Models */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.17 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <GraduationCap className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Training & OSS Models</h2>
        </div>
        <div className="divide-y divide-white/5 mb-4">
          <Toggle
            label="Thinking Tokens"
            description="Enable extended reasoning for supported OSS models (DeepSeek, Qwen)"
            enabled={settings.thinkingTokens as boolean}
            onToggle={() => toggle("thinkingTokens")}
          />
          <Toggle
            label="VRAM-Aware Selection"
            description="Automatically select model size based on available GPU VRAM"
            enabled={settings.vramAware as boolean}
            onToggle={() => toggle("vramAware")}
          />
          <Toggle
            label="Data Collection"
            description="Collect interaction data for self-training (with user consent)"
            enabled={settings.dataCollection as boolean}
            onToggle={() => toggle("dataCollection")}
          />
          <Toggle
            label="Auto-Retrain"
            description="Automatically retrain ML models when new data threshold is met"
            enabled={settings.trainingAutoRetrain as boolean}
            onToggle={() => toggle("trainingAutoRetrain")}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              <span className="flex items-center gap-1">
                <Cpu className="w-3 h-3" />
                OSS Model ID
              </span>
            </label>
            <input
              type="text"
              value={settings.ossModelId}
              onChange={(e) => updateField("ossModelId", e.target.value)}
              placeholder="e.g. deepseek-chat, glm-4, qwen-72b"
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Reasoning Model ID
            </label>
            <input
              type="text"
              value={settings.reasoningModelId}
              onChange={(e) => updateField("reasoningModelId", e.target.value)}
              placeholder="e.g. deepseek-reasoner, qwen-coder"
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Vision Model
            </label>
            <input
              type="text"
              value={settings.visionModel}
              onChange={(e) => updateField("visionModel", e.target.value)}
              placeholder="e.g. glm-4v, qwen-vl"
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Min Training Samples
            </label>
            <input
              type="number"
              value={settings.trainingMinSamples}
              onChange={(e) =>
                updateField("trainingMinSamples", e.target.value)
              }
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* Real-time & Telephony */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Video className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Real-time & Telephony</h2>
        </div>
        <div className="divide-y divide-white/5 mb-4">
          <Toggle
            label="Twilio Integration"
            description="Enable phone calls and SMS via Twilio"
            enabled={settings.twilioEnabled as boolean}
            onToggle={() => toggle("twilioEnabled")}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              <span className="flex items-center gap-1">
                <Video className="w-3 h-3" />
                Video Interval (s)
              </span>
            </label>
            <input
              type="number"
              value={settings.videoAnalysisInterval}
              onChange={(e) =>
                updateField("videoAnalysisInterval", e.target.value)
              }
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                GPS Interval (s)
              </span>
            </label>
            <input
              type="number"
              value={settings.gpsPollInterval}
              onChange={(e) => updateField("gpsPollInterval", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              <span className="flex items-center gap-1">
                <Phone className="w-3 h-3" />
                Emergency (s)
              </span>
            </label>
            <input
              type="number"
              value={settings.emergencyCheckInterval}
              onChange={(e) =>
                updateField("emergencyCheckInterval", e.target.value)
              }
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* Security */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Security</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              CORS Allowed Origins
            </label>
            <input
              type="text"
              value={settings.corsOrigin}
              onChange={(e) => updateField("corsOrigin", e.target.value)}
              placeholder="* or https://yourdomain.com"
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-neutral-400 mb-2">
              Rate Limit (requests/min)
            </label>
            <input
              type="number"
              value={settings.rateLimitRpm}
              onChange={(e) => updateField("rateLimitRpm", e.target.value)}
              className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* Notifications */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4.5 h-4.5 text-cyan-400" />
          <h2 className="text-white font-semibold">Notifications</h2>
        </div>
        <div className="divide-y divide-white/5">
          <Toggle
            label="Push Notifications"
            description="Receive alerts for agent errors and system events"
            enabled={settings.notifications as boolean}
            onToggle={() => toggle("notifications")}
          />
          <Toggle
            label="Usage Analytics"
            description="Collect anonymous usage data to improve the platform"
            enabled={settings.analyticsEnabled as boolean}
            onToggle={() => toggle("analyticsEnabled")}
          />
        </div>
      </motion.div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all">
          <Save className="w-4 h-4" />
          Save Changes
        </button>
        <button className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-neutral-300 border border-white/10 rounded-lg hover:bg-white/5 transition-all">
          <RotateCcw className="w-4 h-4" />
          Reset Defaults
        </button>
      </div>
    </div>
  );
}
