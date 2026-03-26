import { motion } from "framer-motion";
import {
  Stethoscope,
  ShoppingCart,
  Truck,
  Building2,
  Headphones,
  Shield,
} from "lucide-react";
import type { ReactNode } from "react";

interface UseCase {
  icon: ReactNode;
  industry: string;
  title: string;
  description: string;
  tools: string[];
  color: string;
}

const useCases: UseCase[] = [
  {
    icon: <Stethoscope className="w-6 h-6" />,
    industry: "Healthcare",
    title: "Medical triage & appointments",
    description:
      "Patients describe symptoms in natural language. The agent triages urgency, searches practitioners by specialty, checks drug safety, books appointments, and processes orders — with identity verification and insurance coverage checks built in.",
    tools: [
      "search_practitioners",
      "book_appointment",
      "check_drug_safety",
      "medical_chat",
      "analyze_lab_results",
    ],
    color: "from-emerald-500/20 to-green-500/20",
  },
  {
    icon: <ShoppingCart className="w-6 h-6" />,
    industry: "E-commerce",
    title: "AI shopping assistant",
    description:
      "Conversational product search, order creation with delivery fee calculation, balance checks, and payment processing. The agent remembers past orders and suggests reorders. Self-learning optimizes product recommendations over time.",
    tools: [
      "search_products",
      "create_order",
      "check_balance",
      "get_order_history",
      "calculate_delivery_fee",
    ],
    color: "from-purple-500/20 to-pink-500/20",
  },
  {
    icon: <Truck className="w-6 h-6" />,
    industry: "Logistics & Fleet",
    title: "Real-time fleet intelligence",
    description:
      "GPS tracking across your entire fleet with geofence violation alerts. CCTV monitoring at warehouses with AI anomaly detection. Emergency reporting and automatic escalation through 3 severity levels — from push notifications to phone calls.",
    tools: [
      "fleet_overview",
      "check_geofence_violation",
      "detect_anomalies",
      "report_emergency",
      "calculate_route",
    ],
    color: "from-amber-500/20 to-orange-500/20",
  },
  {
    icon: <Headphones className="w-6 h-6" />,
    industry: "Customer Support",
    title: "Autonomous support agents",
    description:
      "Create custom agents that handle tickets end-to-end. They look up orders, draft email replies, manage todos for follow-ups, and escalate when needed. Brain Box memory means they never ask the same question twice.",
    tools: [
      "get_order_history",
      "draft_reply",
      "send_email",
      "create_todo",
      "escalate_emergency",
    ],
    color: "from-blue-500/20 to-cyan-500/20",
  },
  {
    icon: <Building2 className="w-6 h-6" />,
    industry: "Enterprise",
    title: "Internal productivity platform",
    description:
      "Email management (IMAP/SMTP with encryption), calendar scheduling, note-taking with web page summarization, todo lists with AI-prioritized tasks, and document RAG over company policies. All through a single chat interface.",
    tools: [
      "list_emails",
      "create_event",
      "summarize_url",
      "suggest_priorities",
      "query_dataset",
    ],
    color: "from-indigo-500/20 to-violet-500/20",
  },
  {
    icon: <Shield className="w-6 h-6" />,
    industry: "Security & Monitoring",
    title: "Intelligent surveillance",
    description:
      "CCTV video analysis with YOLO object detection or LLM vision (Claude/GPT-4V). Background workers analyze frames continuously, detect anomalies, and trigger emergency alerts. GPS tracking with speed limit monitoring and geofence enforcement.",
    tools: [
      "list_cameras",
      "analyze_frame",
      "detect_anomalies",
      "get_vehicle_position",
      "send_emergency_alert",
    ],
    color: "from-red-500/20 to-rose-500/20",
  },
];

export default function UseCases() {
  return (
    <section id="use-cases" className="relative py-24 px-6">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Built for real industries
          </h2>
          <p className="text-neutral-400 max-w-2xl mx-auto">
            TovaClaw isn't a toy chatbot. It's a production framework deployed
            across healthcare, logistics, e-commerce, and enterprise.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {useCases.map((uc, i) => (
            <motion.div
              key={uc.industry}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              className="group relative rounded-2xl border border-white/5 bg-white/[0.02] overflow-hidden hover:border-white/10 transition-all"
            >
              {/* Gradient header */}
              <div
                className={`bg-gradient-to-br ${uc.color} px-6 py-5`}
              >
                <div className="flex items-center gap-3">
                  <div className="text-white/80">{uc.icon}</div>
                  <div>
                    <div className="text-xs text-white/50 uppercase tracking-wider font-medium">
                      {uc.industry}
                    </div>
                    <div className="text-white font-semibold text-sm">
                      {uc.title}
                    </div>
                  </div>
                </div>
              </div>

              {/* Body */}
              <div className="px-6 py-5">
                <p className="text-sm text-neutral-400 leading-relaxed mb-4">
                  {uc.description}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {uc.tools.map((tool) => (
                    <span
                      key={tool}
                      className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-400/10 text-cyan-400/60"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
