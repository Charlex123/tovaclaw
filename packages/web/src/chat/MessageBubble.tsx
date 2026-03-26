import { Bot, User } from "lucide-react";
import { renderActionCard } from "./cards/CardRegistry";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: string;
  data?: unknown;
  timestamp: string;
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-1 ${
          isUser
            ? "bg-gradient-to-br from-blue-500 to-cyan-500 text-white"
            : "bg-white/5 text-cyan-400"
        }`}
      >
        {isUser ? (
          <User className="w-4 h-4" />
        ) : (
          <Bot className="w-4 h-4" />
        )}
      </div>

      <div className={`flex-1 max-w-[85%] ${isUser ? "flex flex-col items-end" : ""}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-gradient-to-r from-blue-600/20 to-cyan-600/20 border border-blue-500/20 text-neutral-200"
              : "bg-white/[0.03] border border-white/5 text-neutral-300"
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Action card rendered inline below the message */}
        {message.action && message.data
          ? (() => {
              const card = renderActionCard(message.action, message.data);
              return card ? (
                <div className={`w-full ${isUser ? "flex justify-end" : ""}`}>
                  {card}
                </div>
              ) : null;
            })()
          : null}

        <div className={`text-[10px] text-neutral-700 mt-1 ${isUser ? "text-right" : ""}`}>
          {message.timestamp}
        </div>
      </div>
    </div>
  );
}
