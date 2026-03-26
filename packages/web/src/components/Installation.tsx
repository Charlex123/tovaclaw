import { useState } from "react";
import { motion } from "framer-motion";
import CodeBlock from "./CodeBlock";

const pythonInstallOptions = [
  { label: "Anthropic (Claude)", cmd: 'pip install "tova[anthropic]"' },
  { label: "OpenAI (GPT)", cmd: 'pip install "tova[openai]"' },
  { label: "Google (Gemini)", cmd: 'pip install "tova[google]"' },
  { label: "All providers", cmd: 'pip install "tova[all]"' },
];

const pythonQuickStart = `from tova_core.app import create_app
from my_backend import MyBackend, MyStore, MyAuth

app = create_app(
    backend_factory=lambda token: MyBackend(auth_token=token),
    store=MyStore(),
    auth=MyAuth(),
    # Optional feature providers
    email_provider=MyEmail(),
    travel_provider=MyTravel(),
    telephony_provider=MyTwilio(),
)

# Run with: uvicorn main:app --port 8000`;

const pythonStandalone = `# Zero-config standalone mode — no custom providers needed
from tova_core.standalone import create_standalone_app

app = create_standalone_app(llm_provider="anthropic")

# Includes: SQLite store, session auth, travel search,
# email management, todos, notes, calendar, web search,
# Brain Box memory, RAG, and 70+ built-in tools
# Run with: uvicorn main:app --port 8000`;

const nodeQuickStart = `import { TovaClient } from "@tovaclaw/sdk";

const client = new TovaClient({
  baseUrl: "http://localhost:8000",
  token: "your-auth-token",
});

// Chat with the AI agent
const response = await client.chat({
  message: "I need to place an order",
  latitude: 6.5,
  longitude: 3.4,
});

console.log(response.reply);
console.log(response.action, response.data);`;

export default function Installation() {
  const [tab, setTab] = useState<"python" | "node">("python");

  return (
    <section id="installation" className="relative py-24 px-6">
      {/* Subtle divider gradient */}
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
            Up and running in minutes
          </h2>
          <p className="text-neutral-400 max-w-xl mx-auto">
            Run the agent service with Python, or integrate from Node.js with
            the SDK.
          </p>
        </motion.div>

        {/* Language tabs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="flex gap-1 mb-8 p-1 bg-white/[0.02] border border-white/5 rounded-xl w-fit"
        >
          <button
            onClick={() => setTab("python")}
            className={`px-5 py-2 text-sm rounded-lg transition-all ${
              tab === "python"
                ? "bg-white/10 text-white font-medium"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-white/5"
            }`}
          >
            Python
          </button>
          <button
            onClick={() => setTab("node")}
            className={`px-5 py-2 text-sm rounded-lg transition-all ${
              tab === "node"
                ? "bg-white/10 text-white font-medium"
                : "text-neutral-500 hover:text-neutral-300 hover:bg-white/5"
            }`}
          >
            Node.js
          </button>
        </motion.div>

        {tab === "python" ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="mb-8"
            >
              <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
                Choose your LLM provider
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {pythonInstallOptions.map((opt) => (
                  <InstallCard key={opt.label} label={opt.label} cmd={opt.cmd} />
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
                Quick start — custom providers
              </h3>
              <CodeBlock code={pythonQuickStart} language="python" filename="main.py" />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="mt-8"
            >
              <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
                Or use standalone mode
              </h3>
              <CodeBlock code={pythonStandalone} language="python" filename="standalone.py" />
            </motion.div>
          </>
        ) : (
          <>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="mb-8"
            >
              <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
                Install the SDK
              </h3>
              <InstallCard label="npm" cmd="npm install @tovaclaw/sdk" />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
                Quick start
              </h3>
              <CodeBlock code={nodeQuickStart} language="typescript" filename="app.ts" />
            </motion.div>
          </>
        )}
      </div>
    </section>
  );
}

function InstallCard({ label, cmd }: { label: string; cmd: string }) {
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 hover:border-white/10 transition-colors">
      <div className="text-xs text-neutral-500 mb-2">{label}</div>
      <CodeBlock code={cmd} language="bash" />
    </div>
  );
}
