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
  Plane,
  Mail,
  Database,
  Video,
  Phone,
  AlertTriangle,
  Lock,
  Image,
  GraduationCap,
  Shield,
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
    title: "Multi-Agent Runtime",
    description:
      "Define agents with system prompts, tools, triggers, and memory. Each agent is a LangGraph state machine with per-agent LLM overrides.",
  },
  {
    icon: <Plug className="w-5 h-5" />,
    title: "15 Provider Interfaces",
    description:
      "Backend, Store, Auth, Email, Travel, Telephony, Video, Geolocation, VectorStore, FileStore, Image/Video/Audio generation — all pluggable.",
  },
  {
    icon: <Cpu className="w-5 h-5" />,
    title: "Multi-LLM Support",
    description:
      "Claude, GPT, Gemini, or local models via Ollama/vLLM. Per-agent model overrides with a single config change.",
  },
  {
    icon: <Wrench className="w-5 h-5" />,
    title: "70+ Built-in Tools",
    description:
      "Email, travel, todos, notes, events, CCTV, vehicle tracking, emergency, datasets, phone, file management, and web search.",
  },
  {
    icon: <Brain className="w-5 h-5" />,
    title: "Brain Box Memory",
    description:
      "Per-feature, per-user memory namespaces with TTL. Agents remember preferences, facts, and context across isolated memory spaces.",
  },
  {
    icon: <Database className="w-5 h-5" />,
    title: "RAG & Datasets",
    description:
      "Ingest PDFs, DOCX, XLSX, CSVs, images (OCR), and JSON. Query via embeddings with ChromaDB, Pinecone, or Qdrant.",
  },
  {
    icon: <Plane className="w-5 h-5" />,
    title: "Travel & Booking",
    description:
      "Search flights, trains, buses, and car hire with built-in Amadeus and SerpAPI integrations. Compare transport options.",
  },
  {
    icon: <Mail className="w-5 h-5" />,
    title: "Email Management",
    description:
      "IMAP/SMTP integration with encrypted credentials. List, read, categorize, draft, and send emails through natural language.",
  },
  {
    icon: <Video className="w-5 h-5" />,
    title: "Real-time Processing",
    description:
      "Background workers for video analysis, GPS tracking, and emergency monitoring. Continuous anomaly detection.",
  },
  {
    icon: <Phone className="w-5 h-5" />,
    title: "Telephony & SMS",
    description:
      "Twilio-powered phone calls and SMS. Make calls, check status, and send messages through agent conversations.",
  },
  {
    icon: <AlertTriangle className="w-5 h-5" />,
    title: "Emergency System",
    description:
      "Report, escalate, and acknowledge emergencies with real-time monitoring and automatic alert distribution.",
  },
  {
    icon: <Clock className="w-5 h-5" />,
    title: "Scheduler & Events",
    description:
      "Cron-based and event-driven agent execution. Automate follow-ups, digests, and recurring tasks with triggers.",
  },
  {
    icon: <GraduationCap className="w-5 h-5" />,
    title: "Self-Training ML Engine",
    description:
      "7 built-in ML models: intent classifier, anomaly detector, preference predictor, urgency scorer. Learns from every conversation with consent-gated data collection.",
  },
  {
    icon: <Image className="w-5 h-5" />,
    title: "Creative Generation",
    description:
      "Image, video, and audio generation via pluggable providers. Generate content directly from agent conversations.",
  },
  {
    icon: <Lock className="w-5 h-5" />,
    title: "Encrypted Storage",
    description:
      "Fernet encryption for all credentials at rest. Email passwords, API tokens, and user secrets are never stored in plaintext.",
  },
  {
    icon: <Shield className="w-5 h-5" />,
    title: "4 Auth Modes",
    description:
      "Session (anonymous), JWT (production), API Key (service), or None (local). Works with Auth0, Supabase, or any JWT issuer.",
  },
  {
    icon: <Workflow className="w-5 h-5" />,
    title: "Open-Source Models",
    description:
      "First-class support for GLM, DeepSeek, Kimi, Qwen, and more. Thinking tokens, vision models, and VRAM-aware auto-selection.",
  },
  {
    icon: <Globe className="w-5 h-5" />,
    title: "Standalone Mode",
    description:
      "Zero-config launcher with SQLite, session auth, and all built-in features. Run a full agent server in one command.",
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
            A complete multi-agent framework with 15 providers, 70+ tools,
            self-training ML, Brain Box memory, RAG, and encrypted storage.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {features.map((feature, i) => (
            <FeatureCard key={feature.title} feature={feature} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
