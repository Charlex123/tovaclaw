import { motion } from "framer-motion";

interface Endpoint {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  description: string;
}

const endpoints: Endpoint[] = [
  { method: "POST", path: "/agent/chat", description: "Send a message and receive a streaming response" },
  { method: "POST", path: "/agent/execute", description: "Execute an agent action programmatically" },
  { method: "GET", path: "/agent/conversations", description: "List conversations for the authenticated user" },
  { method: "GET", path: "/agent/conversation/{id}", description: "Retrieve full conversation history by ID" },
  { method: "POST", path: "/agents", description: "Create a custom agent with tools, triggers, memory, and brain boxes" },
  { method: "GET", path: "/agents", description: "List all agents owned by the authenticated user" },
  { method: "GET", path: "/agents/{id}", description: "Retrieve agent configuration, tools, and metadata" },
  { method: "PUT", path: "/agents/{id}", description: "Update an existing agent's config, tools, or triggers" },
  { method: "DELETE", path: "/agents/{id}", description: "Delete a custom agent" },
  { method: "POST", path: "/agents/{id}/chat", description: "Chat with a specific custom agent by ID" },
  { method: "GET", path: "/agents/tools", description: "List all available tools in the registry (catalog)" },
  { method: "POST", path: "/datasets/ingest", description: "Ingest PDF, DOCX, CSV, JSON, or images (OCR) into vector store" },
  { method: "GET", path: "/datasets/query", description: "Query ingested datasets via vector similarity search" },
  { method: "POST", path: "/auth/email/connect", description: "Connect email via IMAP with Fernet-encrypted credentials" },
  { method: "GET", path: "/auth/email/status", description: "Check email connection status" },
  { method: "GET", path: "/auth/info", description: "Show current auth configuration (no secrets)" },
  { method: "POST", path: "/auth/keys", description: "Create a new API key (apikey auth mode)" },
  { method: "GET", path: "/health", description: "Health check with service status and version" },
];

const methodColors: Record<string, string> = {
  GET: "bg-green-500/10 text-green-400 border-green-500/20",
  POST: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  PUT: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  DELETE: "bg-red-500/10 text-red-400 border-red-500/20",
};

export default function ApiReference() {
  return (
    <section id="api" className="relative py-24 px-6">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            API Reference
          </h2>
          <p className="text-neutral-400 max-w-xl mx-auto">
            RESTful endpoints for agent interaction, conversation management,
            and custom agent creation.
          </p>
        </motion.div>

        <div className="space-y-3">
          {endpoints.map((ep, i) => (
            <motion.div
              key={ep.path + ep.method}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-20px" }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="group flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04] transition-all"
            >
              <div className="flex items-center gap-3 shrink-0">
                <span
                  className={`inline-flex px-2.5 py-1 text-xs font-mono font-semibold rounded-md border ${methodColors[ep.method]}`}
                >
                  {ep.method}
                </span>
                <code className="text-sm font-mono text-neutral-200">
                  {ep.path}
                </code>
              </div>
              <span className="text-sm text-neutral-500 sm:ml-auto sm:text-right">
                {ep.description}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
