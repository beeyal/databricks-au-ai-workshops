export interface Source {
  tool: string;
  title: string;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: string[];
  sources: Source[];
  streaming: boolean;
}

export interface HealthInfo {
  status: string;
  pt_endpoint: string;
  region: string;
  genie_enabled: boolean;
  lakebase_enabled?: boolean;
}

// SSE event shapes emitted by the backend.
export type AgentEvent =
  | { type: "tool_call"; name: string }
  | { type: "token"; text: string }
  | { type: "final"; content: string; sources: Source[] }
  | { type: "done" };
