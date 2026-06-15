/** Follow-up chat wire types (camelCase, mirroring the backend ApiModel). */

export type ChatRole = "user" | "assistant" | "system";
export type ChatStatus = "streaming" | "complete" | "failed";

export interface Citation {
  sourceIndex: number;
  url: string;
  title: string;
  snippet: string;
}

export interface ChatError {
  code: string;
  message: string;
}

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: ChatRole;
  content: string;
  citations: Citation[];
  createdAt: string;
  finishedAt: string | null;
  status: ChatStatus;
  model: string | null;
  tokensIn: number | null;
  tokensOut: number | null;
  costUsd: number | null;
  error: ChatError | null;
}

export interface ChatListResponse {
  items: ChatMessage[];
  total: number;
}

export interface ChatAccepted {
  messageId: string;
}

export interface ChatSuggestions {
  suggestions: string[];
}
