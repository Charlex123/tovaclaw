import { Github, Heart } from "lucide-react";

export default function Footer() {
  return (
    <footer className="relative border-t border-white/5 py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center font-bold text-white text-sm">
              T
            </div>
            <div>
              <div className="text-white font-semibold">TovaClaw</div>
              <div className="text-xs text-neutral-500">
                Open-source AI agent framework
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <a
              href="https://github.com/charlex123/tovaclaw"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-neutral-400 hover:text-white transition-colors"
            >
              <Github className="w-4 h-4" />
              GitHub
            </a>
            <a
              href="https://pypi.org/project/tova/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-neutral-400 hover:text-white transition-colors"
            >
              PyPI
            </a>
            <a
              href="https://github.com/nosi-ai/tova/blob/main/LICENSE"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-neutral-400 hover:text-white transition-colors"
            >
              License
            </a>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-white/5 text-center">
          <p className="text-xs text-neutral-600 flex items-center justify-center gap-1">
            Built with <Heart className="w-3 h-3 text-red-500/50" /> by the
            Nosi AI team
          </p>
        </div>
      </div>
    </footer>
  );
}
