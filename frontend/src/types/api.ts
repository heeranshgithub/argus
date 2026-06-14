/**
 * Shared API types. The wire format is always camelCase — the backend's
 * naming bridge guarantees no snake_case ever reaches the frontend.
 */

export interface HealthResponse {
  status: "ok" | "down";
  mongo: "ok" | "down";
  version: string;
}

/** The uniform error envelope returned by every backend error response. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
