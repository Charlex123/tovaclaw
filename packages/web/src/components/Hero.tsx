import { motion } from "framer-motion";
import { ArrowRight, Zap } from "lucide-react";

function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Animated gradient orbs */}
      <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-blue-500/10 rounded-full blur-[120px] animate-pulse" />
      <div
        className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-cyan-500/10 rounded-full blur-[120px] animate-pulse"
        style={{ animationDelay: "1s" }}
      />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-indigo-500/5 rounded-full blur-[100px] animate-pulse"
        style={{ animationDelay: "2s" }}
      />

      {/* Grid pattern */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.04]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="white" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      {/* Radial fade */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,#0a0a0a_70%)]" />
    </div>
  );
}

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <GridBackground />

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-24 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 text-sm text-cyan-400 bg-cyan-400/10 border border-cyan-400/20 rounded-full"
        >
          <Zap className="w-3.5 h-3.5" />
          Open-source AI agent framework
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-white leading-[1.1] mb-6"
        >
          AI agents that{" "}
          <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
            learn & act
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-xl text-neutral-400 max-w-2xl mx-auto mb-10 leading-relaxed"
        >
          The open-source multi-agent framework that learns. 70+ tools,
          15 pluggable providers, self-training ML engine, Brain Box memory,
          RAG, real-time monitoring, and encrypted credential storage.
          Build AI agents for any domain in minutes.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <a
            href="#installation"
            className="group flex items-center gap-2 px-6 py-3 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-xl hover:from-blue-500 hover:to-cyan-500 transition-all shadow-lg shadow-blue-500/20"
          >
            Get Started
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="https://github.com/charlex123/tovaclaw"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 text-sm font-medium text-neutral-300 border border-white/10 rounded-xl hover:border-white/20 hover:bg-white/5 transition-all"
          >
            View on GitHub
          </a>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="mt-16 relative"
        >
          <div className="bg-[#111111] border border-white/5 rounded-xl p-6 max-w-2xl mx-auto text-left font-mono text-sm overflow-x-auto">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
              <span className="ml-2 text-xs text-neutral-500">terminal</span>
            </div>
            <div>
              <span className="text-neutral-500">$</span>{" "}
              <span className="text-cyan-400">pip install</span>{" "}
              <span className="text-green-400">"tovaclaw[all]"</span>
            </div>
            <div className="mt-1">
              <span className="text-neutral-500">$</span>{" "}
              <span className="text-cyan-400">tova</span>{" "}
              <span className="text-yellow-400">--standalone</span>
            </div>
            <div className="mt-2 text-neutral-500"># SQLite + 70+ tools + self-learning + encrypted storage</div>
          </div>
          {/* Glow behind terminal */}
          <div className="absolute -inset-4 bg-gradient-to-r from-blue-500/5 to-cyan-500/5 rounded-2xl -z-10 blur-xl" />
        </motion.div>
      </div>
    </section>
  );
}
