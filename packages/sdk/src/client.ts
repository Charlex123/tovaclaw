import {
  type TovaClientOptions,
  type ChatRequest,
  type ChatResponse,
  type ExecuteRequest,
  type ExecuteResponse,
  type HealthResponse,
  type RootResponse,
  type ConversationListResponse,
  type ConversationDetail,
  TovaError,
} from "./types.js";

export class TovaClient {
  private baseUrl: string;
  private token: string | undefined;
  private headers: Record<string, string>;

  constructor(options: TovaClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.token = options.token;
    this.headers = options.headers ?? {};
  }

  /** Update the auth token (e.g. after refresh). */
  setToken(token: string): void {
    this.token = token;
  }

  // ── Internal helpers ──

  private authHeaders(): Record<string, string> {
    const h: Record<string, string> = { ...this.headers };
    if (this.token) {
      h["Authorization"] = `Bearer ${this.token}`;
    }
    return h;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      ...this.authHeaders(),
    };

    const init: RequestInit = { method, headers };

    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }

    const res = await fetch(url, init);

    if (!res.ok) {
      let errBody: unknown;
      try {
        errBody = await res.json();
      } catch {
        errBody = await res.text();
      }
      throw new TovaError(
        `${method} ${path} failed with status ${res.status}`,
        res.status,
        errBody,
      );
    }

    return res.json() as Promise<T>;
  }

  // ── Public API ──

  /** Root status endpoint. */
  async status(): Promise<RootResponse> {
    return this.request("GET", "/");
  }

  /** Health check. */
  async health(): Promise<HealthResponse> {
    return this.request("GET", "/health");
  }

  /** Send a message to the chat agent. */
  async chat(params: ChatRequest): Promise<ChatResponse> {
    return this.request("POST", "/agent/chat", params);
  }

  /** Execute (fulfill) an order. */
  async execute(params: ExecuteRequest): Promise<ExecuteResponse> {
    return this.request("POST", "/agent/execute", params);
  }

  /** List conversations for the authenticated user. */
  async listConversations(): Promise<ConversationListResponse> {
    return this.request("GET", "/agent/conversations");
  }

  /** Get a single conversation's messages. */
  async getConversation(conversationId: string): Promise<ConversationDetail> {
    return this.request(
      "GET",
      `/agent/conversation/${encodeURIComponent(conversationId)}`,
    );
  }
}
