/**
 * Session wire types. The backend's naming bridge guarantees camelCase, so
 * these mirror `SessionOut` on the server.
 */

export type SessionStatus = "created" | "running" | "completed" | "failed";

export interface Session {
  id: string;
  companyName: string;
  website: string;
  objective: string;
  status: SessionStatus;
  isVisible: boolean;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

export interface SessionListResponse {
  items: Session[];
  total: number;
}
