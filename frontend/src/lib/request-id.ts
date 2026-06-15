/**
 * Tracks the `X-Request-ID` of the most recent API response so error boundaries
 * can surface it for support/correlation (PLAN_PART_5 §2.2). Updated by the RTK
 * Query `fetchFn` wrapper in `services/api.ts`.
 */

let lastRequestId: string | null = null;

export function setLastRequestId(id: string): void {
  lastRequestId = id;
}

export function getLastRequestId(): string | null {
  return lastRequestId;
}
