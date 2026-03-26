import { motion } from "framer-motion";
import {
  Bot,
  MessageSquare,
  Plug,
  Wrench,
  Brain,
  Database,
  Activity,
  Clock,
} from "lucide-react";
import StatsCard from "../components/StatsCard.tsx";

const recentActivity = [
  {
    action: "Agent created",
    detail: "healthcare-assistant",
    time: "2 min ago",
  },
  {
    action: "Email connected",
    detail: "IMAP — user@company.com",
    time: "10 min ago",
  },
  {
    action: "API key added",
    detail: "Anthropic (Claude)",
    time: "15 min ago",
  },
  {
    action: "Document ingested",
    detail: "policies.pdf — 24 chunks",
    time: "30 min ago",
  },
  {
    action: "Brain Box memory",
    detail: "email namespace — 12 entries",
    time: "1 hr ago",
  },
  {
    action: "Travel search",
    detail: "LOS → LHR — 8 flights found",
    time: "2 hrs ago",
  },
  {
    action: "Agent updated",
    detail: "support-bot — added triggers",
    time: "3 hrs ago",
  },
  {
    action: "Emergency alert",
    detail: "escalated — priority high",
    time: "4 hrs ago",
  },
];

export default function Overview() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatsCard
          icon={<Bot className="w-4.5 h-4.5" />}
          label="Active Agents"
          value="4"
          change="+2 this week"
          changeType="positive"
          index={0}
        />
        <StatsCard
          icon={<MessageSquare className="w-4.5 h-4.5" />}
          label="Conversations"
          value="1,284"
          change="+12%"
          changeType="positive"
          index={1}
        />
        <StatsCard
          icon={<Plug className="w-4.5 h-4.5" />}
          label="Providers"
          value="6 / 12"
          change="Connected"
          changeType="neutral"
          index={2}
        />
        <StatsCard
          icon={<Wrench className="w-4.5 h-4.5" />}
          label="Tools"
          value="73"
          change="14 categories"
          changeType="neutral"
          index={3}
        />
        <StatsCard
          icon={<Brain className="w-4.5 h-4.5" />}
          label="Brain Box"
          value="51"
          change="7 namespaces"
          changeType="neutral"
          index={4}
        />
        <StatsCard
          icon={<Database className="w-4.5 h-4.5" />}
          label="Database"
          value="Connected"
          change="SQLite"
          changeType="neutral"
          index={5}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="lg:col-span-2 p-6 rounded-xl border border-white/5 bg-white/[0.02]"
        >
          <div className="flex items-center gap-2 mb-5">
            <Activity className="w-4.5 h-4.5 text-cyan-400" />
            <h2 className="text-white font-semibold">Recent Activity</h2>
          </div>
          <div className="space-y-3">
            {recentActivity.map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0"
              >
                <div>
                  <span className="text-sm text-white">{item.action}</span>
                  <span className="text-sm text-neutral-500 ml-2">
                    {item.detail}
                  </span>
                </div>
                <span className="text-xs text-neutral-600 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {item.time}
                </span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="p-6 rounded-xl border border-white/5 bg-white/[0.02]"
        >
          <h2 className="text-white font-semibold mb-5">Quick Actions</h2>
          <div className="space-y-2">
            {[
              { label: "Create Agent", href: "/agents" },
              { label: "Configure Providers", href: "/providers" },
              { label: "Browse Tools", href: "/tools" },
              { label: "View Brain Box", href: "/brain-box" },
              { label: "Add API Key", href: "/api-keys" },
              { label: "Configure Database", href: "/database" },
            ].map((action) => (
              <a
                key={action.label}
                href={action.href}
                className="block px-4 py-3 text-sm text-neutral-300 hover:text-white rounded-lg border border-white/5 hover:border-white/10 hover:bg-white/[0.04] transition-all"
              >
                {action.label}
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
