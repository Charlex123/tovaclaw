import { useState, useRef, useEffect } from "react";
import { Send, Paperclip, Mic } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-white/5 bg-[#0d0d0d] p-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 p-2 rounded-2xl border border-white/10 bg-white/[0.03] focus-within:border-blue-500/30 transition-colors">
          <button className="p-2 text-neutral-500 hover:text-neutral-300 rounded-lg hover:bg-white/5 transition-colors shrink-0">
            <Paperclip className="w-4.5 h-4.5" />
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder ?? "Ask anything — travel, email, orders, tasks..."}
            disabled={disabled}
            rows={1}
            className="flex-1 bg-transparent text-sm text-neutral-200 placeholder:text-neutral-600 resize-none outline-none py-2 max-h-40 leading-relaxed"
          />
          <button className="p-2 text-neutral-500 hover:text-neutral-300 rounded-lg hover:bg-white/5 transition-colors shrink-0">
            <Mic className="w-4.5 h-4.5" />
          </button>
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || disabled}
            className="p-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 text-white hover:from-blue-500 hover:to-cyan-500 transition-all disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            <Send className="w-4.5 h-4.5" />
          </button>
        </div>
        <div className="text-center mt-2">
          <span className="text-[10px] text-neutral-700">
            Powered by TovaClaw — 70+ tools, 15 providers, multi-LLM
          </span>
        </div>
      </div>
    </div>
  );
}
