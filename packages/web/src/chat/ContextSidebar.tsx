import {
  Brain,
  MessageSquare,
  Clock,
  Sparkles,
  ChevronRight,
} from "lucide-react";

interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  time: string;
}

interface MemoryEntry {
  key: string;
  value: string;
  feature: string;
}

interface ContextSidebarProps {
  conversations: Conversation[];
  activeConversation: string | null;
  onSelectConversation: (id: string) => void;
  memories: MemoryEntry[];
  activeFeatures: string[];
}

export default function ContextSidebar({
  conversations,
  activeConversation,
  onSelectConversation,
  memories,
  activeFeatures,
}: ContextSidebarProps) {
  return (
    <aside className="w-72 border-l border-white/5 bg-[#0d0d0d] flex flex-col overflow-hidden shrink-0 hidden xl:flex">
      {/* Active Features */}
      <div className="p-4 border-b border-white/5">
        <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 uppercase tracking-wider mb-3">
          <Sparkles className="w-3 h-3" />
          Active Features
        </div>
        <div className="flex flex-wrap gap-1.5">
          {activeFeatures.map((feature) => (
            <span
              key={feature}
              className="px-2 py-1 text-xs text-cyan-400 bg-cyan-400/10 rounded-lg"
            >
              {feature}
            </span>
          ))}
        </div>
      </div>

      {/* Brain Box Memories */}
      <div className="p-4 border-b border-white/5">
        <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 uppercase tracking-wider mb-3">
          <Brain className="w-3 h-3" />
          Brain Box
        </div>
        <div className="space-y-2">
          {memories.length === 0 ? (
            <div className="text-xs text-neutral-600">
              No memories yet. I'll learn your preferences as we chat.
            </div>
          ) : (
            memories.map((m, i) => (
              <div
                key={i}
                className="p-2 rounded-lg bg-white/[0.02] border border-white/5"
              >
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-[10px] text-cyan-400/50 font-mono">
                    {m.feature}
                  </span>
                  <ChevronRight className="w-2.5 h-2.5 text-neutral-700" />
                  <span className="text-[10px] text-neutral-500 font-mono">
                    {m.key}
                  </span>
                </div>
                <div className="text-xs text-neutral-400">{m.value}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 uppercase tracking-wider mb-3">
            <MessageSquare className="w-3 h-3" />
            Conversations
          </div>
          <div className="space-y-1">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`w-full text-left p-2.5 rounded-lg transition-all ${
                  activeConversation === conv.id
                    ? "bg-blue-500/10 border border-blue-500/20"
                    : "hover:bg-white/[0.03] border border-transparent"
                }`}
              >
                <div className="text-sm text-neutral-300 truncate">
                  {conv.title}
                </div>
                <div className="text-xs text-neutral-600 truncate mt-0.5">
                  {conv.lastMessage}
                </div>
                <div className="flex items-center gap-1 mt-1 text-[10px] text-neutral-700">
                  <Clock className="w-2.5 h-2.5" />
                  {conv.time}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
