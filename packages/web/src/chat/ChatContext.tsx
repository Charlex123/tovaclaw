import { createContext, useContext } from "react";

interface ChatActions {
  /** Send a message as the user (shows user bubble + triggers agent response) */
  sendMessage: (text: string) => void;
  /** Trigger an agent response directly (no user bubble) */
  triggerResponse: (action: string, content: string, data?: unknown) => void;
}

export const ChatContext = createContext<ChatActions>({
  sendMessage: () => {},
  triggerResponse: () => {},
});

export function useChatActions() {
  return useContext(ChatContext);
}
