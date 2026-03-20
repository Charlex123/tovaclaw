import { motion } from "framer-motion";
import CodeBlock from "./CodeBlock";

const installOptions = [
  { label: "Anthropic (Claude)", cmd: 'pip install "tova[anthropic]"' },
  { label: "OpenAI (GPT)", cmd: 'pip install "tova[openai]"' },
  { label: "Google (Gemini)", cmd: 'pip install "tova[google]"' },
  { label: "All providers", cmd: 'pip install "tova[all]"' },
];

const quickStart = `from tova_core.app import create_app
from my_backend import MyBackend, MyStore, MyAuth

app = create_app(
    backend_factory=lambda token: MyBackend(auth_token=token),
    store=MyStore(),
    auth=MyAuth(),
)

# Run with: uvicorn main:app --port 8000`;

export default function Installation() {
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
            Install with pip, wire up your backend, and start building
            AI-powered agents.
          </p>
        </motion.div>

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
            {installOptions.map((opt) => (
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
            Quick start
          </h3>
          <CodeBlock code={quickStart} language="python" filename="main.py" />
        </motion.div>
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
