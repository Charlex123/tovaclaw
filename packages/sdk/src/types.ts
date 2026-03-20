// ── Request types ──

export interface ChatRequest {
  message: string;
  conversation_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface ExecuteRequest {
  order_id: string;
}

// ── Response types ──

export type ChatAction =
  | "product_results"
  | "service_results"
  | "practitioner_results"
  | "order_created"
  | "order_cancelled"
  | "order_executed"
  | "appointment_booked"
  | "appointment_cancelled"
  | "order_history"
  | "appointment_history"
  | "balance_check"
  | "drug_safety"
  | "confirmation_needed"
  | "info_needed"
  | "insufficient_balance"
  | "error";

export interface ChatResponse {
  reply: string;
  action: ChatAction | null;
  data: Record<string, unknown> | null;
  conversation_id: string;
  tools_used: string[];
}

export interface ExecuteResponse {
  success: boolean;
  message: string;
  tools_used: string[];
  alternatives_found: boolean;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface RootResponse {
  service: string;
  version: string;
  status: string;
  docs: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
  created_at: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  action?: string | null;
  data?: Record<string, unknown> | null;
  timestamp: string;
}

export interface ConversationDetail {
  conversation_id: string;
  messages: ConversationMessage[];
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

// ── Client options ──

export interface TovaClientOptions {
  baseUrl: string;
  token?: string;
  headers?: Record<string, string>;
}

// ── Error ──

export class TovaError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "TovaError";
    this.status = status;
    this.body = body;
  }
}
