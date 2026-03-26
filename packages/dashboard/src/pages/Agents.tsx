import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Plus,
  MoreVertical,
  Play,
  Pause,
  Trash2,
  Settings,
  MessageSquare,
  Clock,
  X,
} from "lucide-react";

interface Agent {
  id: string;
  name: string;
  description: string;
  status: "running" | "stopped" | "error";
  model: string;
  conversations: number;
  lastActive: string;
  tools?: string[];
  trigger?: string;
  memoryEnabled?: boolean;
}

const initialAgents: Agent[] = [
  {
    id: "1",
    name: "healthcare-assistant",
    description:
      "Medical triage and appointment scheduling agent for clinic portals",
    status: "running",
    model: "claude-sonnet-4",
    conversations: 342,
    lastActive: "2 min ago",
    tools: ["search_products", "book_appointment", "check_balance", "medical_chat"],
    trigger: "event:appointment_request",
    memoryEnabled: true,
  },
  {
    id: "2",
    name: "support-bot",
    description: "Customer support with order tracking, email, and escalation",
    status: "running",
    model: "gpt-4o",
    conversations: 891,
    lastActive: "5 min ago",
    tools: ["get_order_history", "search_products", "list_emails", "send_email"],
    memoryEnabled: true,
  },
  {
    id: "3",
    name: "travel-planner",
    description:
      "Flight, train, and hotel search with itinerary management",
    status: "running",
    model: "claude-sonnet-4",
    conversations: 156,
    lastActive: "15 min ago",
    tools: ["search_flights", "search_trains", "compare_transport", "search_accommodations"],
    memoryEnabled: true,
  },
  {
    id: "4",
    name: "security-monitor",
    description:
      "CCTV analysis, emergency detection, and fleet tracking agent",
    status: "stopped",
    model: "claude-haiku-4",
    conversations: 28,
    lastActive: "1 day ago",
    tools: ["list_cameras", "analyze_frame", "detect_anomalies", "report_emergency"],
    trigger: "cron:*/5 * * * *",
  },
];

const statusStyles = {
  running: {
    dot: "bg-green-400",
    label: "Running",
    badge: "text-green-400 bg-green-400/10",
  },
  stopped: {
    dot: "bg-neutral-500",
    label: "Stopped",
    badge: "text-neutral-400 bg-neutral-400/10",
  },
  error: {
    dot: "bg-red-400",
    label: "Error",
    badge: "text-red-400 bg-red-400/10",
  },
};

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [showCreate, setShowCreate] = useState(false);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [newAgent, setNewAgent] = useState({
    name: "",
    description: "",
    model: "claude-sonnet-4",
    tools: "",
    trigger: "",
    memoryEnabled: true,
    personality: "",
    greeting: "",
    brainBoxes: "",
  });

  const toggleAgent = (id: string) => {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === id
          ? { ...a, status: a.status === "running" ? "stopped" : "running" }
          : a
      )
    );
  };

  const deleteAgent = (id: string) => {
    setAgents((prev) => prev.filter((a) => a.id !== id));
    setMenuOpen(null);
  };

  const createAgent = () => {
    if (!newAgent.name.trim()) return;
    const agent: Agent = {
      id: Date.now().toString(),
      name: newAgent.name,
      description: newAgent.description,
      status: "stopped",
      model: newAgent.model,
      conversations: 0,
      lastActive: "just now",
      tools: newAgent.tools
        ? newAgent.tools.split(",").map((t) => t.trim())
        : undefined,
      trigger: newAgent.trigger || undefined,
      memoryEnabled: newAgent.memoryEnabled,
    };
    setAgents((prev) => [...prev, agent]);
    setNewAgent({
      name: "",
      description: "",
      model: "claude-sonnet-4",
      tools: "",
      trigger: "",
      memoryEnabled: true,
      personality: "",
      greeting: "",
      brainBoxes: "",
    });
    setShowCreate(false);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">
          Create and manage AI agents. Each agent has its own configuration,
          tools, and conversation history.
        </p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Agent
        </button>
      </div>

      <div className="space-y-3">
        {agents.map((agent, i) => {
          const style = statusStyles[agent.status];
          return (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="p-5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400 mt-0.5">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-white font-medium font-mono text-sm">
                        {agent.name}
                      </h3>
                      <span
                        className={`flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${style.badge}`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${style.dot}`}
                        />
                        {style.label}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-500 mt-1 max-w-lg">
                      {agent.description}
                    </p>
                    {agent.tools && agent.tools.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {agent.tools.slice(0, 4).map((tool) => (
                          <span
                            key={tool}
                            className="text-xs font-mono px-1.5 py-0.5 rounded bg-cyan-400/10 text-cyan-400/70"
                          >
                            {tool}
                          </span>
                        ))}
                        {agent.tools.length > 4 && (
                          <span className="text-xs text-neutral-600">
                            +{agent.tools.length - 4} more
                          </span>
                        )}
                      </div>
                    )}
                    <div className="flex items-center gap-4 mt-3 text-xs text-neutral-600">
                      <span className="flex items-center gap-1">
                        <Settings className="w-3 h-3" />
                        {agent.model}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        {agent.conversations} conversations
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {agent.lastActive}
                      </span>
                      {agent.trigger && (
                        <span className="text-amber-400/60">
                          {agent.trigger}
                        </span>
                      )}
                      {agent.memoryEnabled && (
                        <span className="text-purple-400/60">
                          memory: on
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleAgent(agent.id)}
                    className="p-2 text-neutral-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                    title={
                      agent.status === "running" ? "Stop agent" : "Start agent"
                    }
                  >
                    {agent.status === "running" ? (
                      <Pause className="w-4 h-4" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                  <div className="relative">
                    <button
                      onClick={() =>
                        setMenuOpen(menuOpen === agent.id ? null : agent.id)
                      }
                      className="p-2 text-neutral-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {menuOpen === agent.id && (
                      <div className="absolute right-0 top-10 w-40 py-1 rounded-lg border border-white/10 bg-[#1a1a1a] shadow-xl z-10">
                        <button className="w-full px-4 py-2 text-sm text-neutral-300 hover:text-white hover:bg-white/5 text-left flex items-center gap-2">
                          <Settings className="w-3.5 h-3.5" />
                          Configure
                        </button>
                        <button
                          onClick={() => deleteAgent(agent.id)}
                          className="w-full px-4 py-2 text-sm text-red-400 hover:bg-red-400/10 text-left flex items-center gap-2"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Create Agent Modal */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
            onClick={() => setShowCreate(false)}
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
                  Create Agent
                </h3>
                <button
                  onClick={() => setShowCreate(false)}
                  className="p-1 text-neutral-500 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Agent Name
                  </label>
                  <input
                    type="text"
                    value={newAgent.name}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        name: e.target.value,
                      }))
                    }
                    placeholder="my-agent"
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Description
                  </label>
                  <textarea
                    value={newAgent.description}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                    placeholder="What does this agent do?"
                    rows={3}
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Model
                  </label>
                  <select
                    value={newAgent.model}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        model: e.target.value,
                      }))
                    }
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                  >
                    <option value="claude-sonnet-4" className="bg-[#1a1a1a]">
                      Claude Sonnet 4
                    </option>
                    <option value="claude-opus-4" className="bg-[#1a1a1a]">
                      Claude Opus 4
                    </option>
                    <option value="claude-haiku-4" className="bg-[#1a1a1a]">
                      Claude Haiku 4
                    </option>
                    <option value="gpt-4o" className="bg-[#1a1a1a]">
                      GPT-4o
                    </option>
                    <option
                      value="gemini-2.0-flash"
                      className="bg-[#1a1a1a]"
                    >
                      Gemini 2.0 Flash
                    </option>
                    <option value="local" className="bg-[#1a1a1a]">
                      Local (Ollama / vLLM)
                    </option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Tools (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={newAgent.tools}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        tools: e.target.value,
                      }))
                    }
                    placeholder="search_products, create_order, send_email"
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Trigger (optional)
                  </label>
                  <input
                    type="text"
                    value={newAgent.trigger}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        trigger: e.target.value,
                      }))
                    }
                    placeholder="cron:0 9 * * 1 or event:ticket_created"
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Personality / System Prompt
                  </label>
                  <textarea
                    value={newAgent.personality}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        personality: e.target.value,
                      }))
                    }
                    placeholder="You are a helpful travel planning assistant..."
                    rows={2}
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors resize-none"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Greeting Message
                  </label>
                  <input
                    type="text"
                    value={newAgent.greeting}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        greeting: e.target.value,
                      }))
                    }
                    placeholder="Hi! I'm your travel planner. Where to next?"
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-2">
                    Brain Boxes (comma-separated namespaces)
                  </label>
                  <input
                    type="text"
                    value={newAgent.brainBoxes}
                    onChange={(e) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        brainBoxes: e.target.value,
                      }))
                    }
                    placeholder="email, travel, preferences"
                    className="w-full px-4 py-2.5 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono"
                  />
                </div>

                <div className="flex items-center justify-between py-1">
                  <div>
                    <div className="text-sm text-white">Brain Box Memory</div>
                    <div className="text-xs text-neutral-500 mt-0.5">
                      Enable per-user memory for this agent
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setNewAgent((prev) => ({
                        ...prev,
                        memoryEnabled: !prev.memoryEnabled,
                      }))
                    }
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      newAgent.memoryEnabled ? "bg-blue-500" : "bg-neutral-700"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                        newAgent.memoryEnabled
                          ? "translate-x-5"
                          : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                <button
                  onClick={createAgent}
                  className="w-full py-2.5 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all mt-2"
                >
                  Create Agent
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
