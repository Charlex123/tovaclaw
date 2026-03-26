import { Mail, Send, Edit3 } from "lucide-react";
import { useChatActions } from "../ChatContext";

interface EmailDraft {
  to: string;
  subject: string;
  body: string;
  from?: string;
}

interface EmailList {
  emails: { from: string; subject: string; date: string; preview: string; read: boolean }[];
}

export function EmailDraftCard({ data }: { data: EmailDraft }) {
  const { sendMessage } = useChatActions();

  return (
    <div className="mt-2 rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/5 bg-white/[0.01]">
        <Mail className="w-4 h-4 text-cyan-400" />
        <span className="text-sm text-white font-medium">Email Draft</span>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-neutral-500 w-12 shrink-0">To:</span>
          <span className="text-white">{data.to}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-neutral-500 w-12 shrink-0">Subject:</span>
          <span className="text-white">{data.subject}</span>
        </div>
        <div className="text-sm text-neutral-300 leading-relaxed whitespace-pre-wrap border-t border-white/5 pt-3">
          {data.body}
        </div>
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => sendMessage(`Send this email to ${data.to}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-lg hover:from-blue-500 hover:to-cyan-500 transition-all"
          >
            <Send className="w-3 h-3" />
            Send
          </button>
          <button
            onClick={() => sendMessage(`Edit the draft email to ${data.to} about "${data.subject}"`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-neutral-300 border border-white/10 rounded-lg hover:bg-white/5 transition-all"
          >
            <Edit3 className="w-3 h-3" />
            Edit
          </button>
        </div>
      </div>
    </div>
  );
}

export function EmailListCard({ data }: { data: EmailList }) {
  const { sendMessage } = useChatActions();
  const emails = data.emails ?? [];

  return (
    <div className="mt-2 space-y-1">
      {emails.map((e, i) => (
        <button
          key={i}
          onClick={() => sendMessage(`Read email from ${e.from}: "${e.subject}"`)}
          className={`w-full text-left flex items-start gap-3 p-3 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors ${
            !e.read ? "border-l-2 border-l-cyan-500/50" : ""
          }`}
        >
          <Mail className={`w-4 h-4 mt-0.5 shrink-0 ${e.read ? "text-neutral-600" : "text-cyan-400"}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className={`text-sm truncate ${e.read ? "text-neutral-400" : "text-white font-medium"}`}>
                {e.from}
              </span>
              <span className="text-xs text-neutral-600 shrink-0">{e.date}</span>
            </div>
            <div className={`text-sm truncate ${e.read ? "text-neutral-500" : "text-neutral-300"}`}>
              {e.subject}
            </div>
            <div className="text-xs text-neutral-600 truncate mt-0.5">{e.preview}</div>
          </div>
        </button>
      ))}
    </div>
  );
}
