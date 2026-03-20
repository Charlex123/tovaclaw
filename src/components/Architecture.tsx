import { motion } from "framer-motion";

const layers = [
  {
    label: "Client Interface",
    sublabel: "REST API / WebSocket",
    color: "from-blue-500/20 to-blue-500/5",
    borderColor: "border-blue-500/20",
    textColor: "text-blue-400",
  },
  {
    label: "Tova Agent",
    sublabel: "LangGraph State Machine",
    color: "from-cyan-500/20 to-cyan-500/5",
    borderColor: "border-cyan-500/20",
    textColor: "text-cyan-400",
  },
  {
    label: "Tool Registry",
    sublabel: "Your Tools  |  Actions  |  Integrations  |  Workflows",
    color: "from-indigo-500/20 to-indigo-500/5",
    borderColor: "border-indigo-500/20",
    textColor: "text-indigo-400",
  },
  {
    label: "Provider Layer",
    sublabel: "BaseBackend  |  BaseStore  |  BaseAuth  |  BaseNotifier",
    color: "from-purple-500/20 to-purple-500/5",
    borderColor: "border-purple-500/20",
    textColor: "text-purple-400",
  },
  {
    label: "Infrastructure",
    sublabel: "Your Database  |  Your Auth  |  Your APIs  |  Any LLM",
    color: "from-pink-500/20 to-pink-500/5",
    borderColor: "border-pink-500/20",
    textColor: "text-pink-400",
  },
];

export default function Architecture() {
  return (
    <section id="architecture" className="relative py-24 px-6">
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
            Layered architecture
          </h2>
          <p className="text-neutral-400 max-w-2xl mx-auto">
            Each layer is pluggable. Implement the interfaces that matter to
            your system, and Tova handles the rest.
          </p>
        </motion.div>

        <div className="relative max-w-2xl mx-auto">
          {/* Connecting lines */}
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-blue-500/20 via-purple-500/20 to-pink-500/20" />

          <div className="space-y-4">
            {layers.map((layer, i) => (
              <motion.div
                key={layer.label}
                initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-30px" }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="relative"
              >
                {/* Connector dot */}
                <div
                  className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-gradient-to-br ${layer.color} border ${layer.borderColor} z-10`}
                />

                <div
                  className={`relative rounded-xl border ${layer.borderColor} bg-gradient-to-r ${layer.color} backdrop-blur-sm p-5 ml-8 sm:ml-0`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                    <h3 className={`font-semibold ${layer.textColor}`}>
                      {layer.label}
                    </h3>
                    <span className="text-xs text-neutral-500 font-mono">
                      {layer.sublabel}
                    </span>
                  </div>
                </div>

                {/* Arrow down */}
                {i < layers.length - 1 && (
                  <div className="flex justify-center my-1">
                    <svg
                      width="12"
                      height="16"
                      viewBox="0 0 12 16"
                      className="text-neutral-600"
                    >
                      <path
                        d="M6 0v12M1 9l5 5 5-5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Provider boxes */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-3"
        >
          {[
            { name: "BaseBackend", desc: "Your domain logic" },
            { name: "BaseStore", desc: "Persistence layer" },
            { name: "BaseAuth", desc: "Token validation" },
            { name: "BaseNotifier", desc: "Push / SMS / Email" },
          ].map((p) => (
            <div
              key={p.name}
              className="text-center p-4 rounded-xl border border-white/5 bg-white/[0.02]"
            >
              <div className="font-mono text-sm text-cyan-400 mb-1">
                {p.name}
              </div>
              <div className="text-xs text-neutral-500">{p.desc}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
