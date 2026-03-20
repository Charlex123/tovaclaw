import { motion } from "framer-motion";
import { Package, Zap, Shield, Code2 } from "lucide-react";
import CodeBlock from "./CodeBlock";

const highlights = [
  {
    icon: Package,
    title: "Zero Dependencies",
    desc: "Uses native fetch — no axios, no bloat. Works in Node.js 18+, Bun, and Deno.",
  },
  {
    icon: Code2,
    title: "Full TypeScript Types",
    desc: "Every request, response, and action type is exported. Autocomplete out of the box.",
  },
  {
    icon: Zap,
    title: "Tiny Footprint",
    desc: "Under 3 KB minified. Ships as both ESM and CommonJS.",
  },
  {
    icon: Shield,
    title: "Error Handling",
    desc: "Typed TovaError with status codes and response bodies for clean error flows.",
  },
];

const installSnippet = `npm install @tovaclaw/sdk`;

const exampleSnippet = `import { TovaClient, TovaError } from "@tovaclaw/sdk";

const client = new TovaClient({
  baseUrl: "https://api.yourapp.com",
  token: session.jwt,
});

try {
  const res = await client.chat({
    message: "Track order #4521",
  });

  switch (res.action) {
    case "order_history":
      renderOrderCard(res.data);
      break;
    case "confirmation_needed":
      showConfirmDialog(res.reply);
      break;
    default:
      showMessage(res.reply);
  }
} catch (err) {
  if (err instanceof TovaError) {
    console.error(err.status, err.body);
  }
}`;

export default function SdkSection() {
  return (
    <section id="sdk" className="relative py-24 px-6">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/5 text-cyan-400 text-xs font-medium mb-6">
            <Package className="w-3.5 h-3.5" />
            @tovaclaw/sdk
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Node.js SDK
          </h2>
          <p className="text-neutral-400 max-w-xl mx-auto">
            A lightweight TypeScript client that wraps every Tova endpoint.
            Install it, pass a token, and start building.
          </p>
        </motion.div>

        {/* Highlights grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-12"
        >
          {highlights.map((h) => (
            <div
              key={h.title}
              className="flex gap-4 p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/10 transition-colors"
            >
              <div className="shrink-0 w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                <h.icon className="w-4.5 h-4.5 text-cyan-400" />
              </div>
              <div>
                <div className="text-sm font-medium text-white mb-1">
                  {h.title}
                </div>
                <div className="text-xs text-neutral-500 leading-relaxed">
                  {h.desc}
                </div>
              </div>
            </div>
          ))}
        </motion.div>

        {/* Install */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="mb-8"
        >
          <CodeBlock code={installSnippet} language="bash" />
        </motion.div>

        {/* Full example */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-sm font-medium text-neutral-400 uppercase tracking-wider mb-4">
            Example integration
          </h3>
          <CodeBlock
            code={exampleSnippet}
            language="typescript"
            filename="app.ts"
          />
        </motion.div>
      </div>
    </section>
  );
}
