import { motion } from "framer-motion";
import {
  MessageSquare,
  Cpu,
  Wrench,
  Brain,
  Clock,
  Workflow,
  Plug,
  Globe,
} from "lucide-react";
import type { ReactNode } from "react";

interface Feature {
  icon: ReactNode;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: <MessageSquare className="w-5 h-5" />,
    title: "Custom Agents",
    description:
      "Define agents with system prompts, tools, and workflows. Each agent is a LangGraph state machine you fully control.",
  },
  {
    icon: <Plug className="w-5 h-5" />,
    title: "Provider Pattern",
    description:
      "Pluggable BaseBackend, BaseStore, BaseAuth, and BaseNotifier interfaces let you connect any backend, database, or auth system.",
  },
  {
    icon: <Cpu className="w-5 h-5" />,
    title: "Multi-LLM Support",
    description:
      "Swap between Claude, GPT, Gemini, or local models with a single config change. No vendor lock-in.",
  },
  {
    icon: <Wrench className="w-5 h-5" />,
    title: "Pluggable Tool System",
    description:
      "ToolRegistry and ToolDefinition APIs let you register custom tools the agent can invoke during conversations.",
  },
  {
    icon: <Brain className="w-5 h-5" />,
    title: "Agent Memory",
    description:
      "Persistent context across sessions. Agents remember user preferences, past interactions, and conversation history.",
  },
  {
    icon: <Clock className="w-5 h-5" />,
    title: "Scheduler & Events",
    description:
      "Schedule agent executions on a cron or trigger them from events. Automate follow-ups, notifications, and recurring tasks.",
  },
  {
    icon: <Workflow className="w-5 h-5" />,
    title: "Workflow Automation",
    description:
      "Chain tools and agents into multi-step workflows. Handle approvals, escalations, and conditional branching out of the box.",
  },
  {
    icon: <Globe className="w-5 h-5" />,
    title: "REST API",
    description:
      "FastAPI-based with streaming chat, agent management, and conversation endpoints. Deploy anywhere with uvicorn.",
  },
];

function FeatureCard({ feature, index }: { feature: Feature; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay: index * 0.05 }}
      className="group relative p-6 rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-sm hover:bg-white/[0.04] hover:border-white/10 transition-all duration-300"
    >
      {/* Hover glow */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="relative z-10">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4">
          {feature.icon}
        </div>
        <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
        <p className="text-sm text-neutral-400 leading-relaxed">
          {feature.description}
        </p>
      </div>
    </motion.div>
  );
}

export default function Features() {
  return (
    <section id="features" className="relative py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Everything you need to build AI agents
          </h2>
          <p className="text-neutral-400 max-w-2xl mx-auto">
            A complete framework with pluggable architecture, multi-LLM support,
            and production-ready patterns for any domain.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((feature, i) => (
            <FeatureCard key={feature.title} feature={feature} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
