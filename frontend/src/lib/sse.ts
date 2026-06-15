/**
 * Tiny `EventSource` wrapper for the run-events stream.
 *
 * The backend sends *named* SSE events (`event: node_started`, …) whose JSON
 * `data` is a full `WorkflowEvent`. Native `EventSource` only surfaces named
 * events through `addEventListener`, so we register one listener per kind.
 *
 * We manage reconnection ourselves (rather than letting `EventSource` retry) so
 * each reconnect can carry the latest `since_seq` — the backend replays only
 * events past it, guaranteeing no gap and no duplicate after a dropped
 * connection. Backoff is exponential (1s → 2s → 4s, capped at 10s).
 */

import type { EventKind, WorkflowEvent } from "@/types/workflow";

const EVENT_KINDS: readonly EventKind[] = [
  "run_started",
  "run_completed",
  "run_failed",
  "node_started",
  "node_finished",
  "node_errored",
  "node_output",
];

const MAX_BACKOFF_MS = 10_000;

export interface OpenEventStreamOptions {
  onEvent: (event: WorkflowEvent) => void;
  onOpen?: () => void;
  onError?: (err: unknown) => void;
  /** Resume point; only events with `seq > sinceSeq` are (re)delivered. */
  sinceSeq?: number;
}

/**
 * Open a resilient SSE stream to `baseUrl` (an absolute events endpoint).
 * Returns an `unsubscribe()` that closes the stream and cancels any pending
 * reconnect. Safe to call during SSR — it no-ops without a browser
 * `EventSource`.
 */
export function openEventStream(
  baseUrl: string,
  opts: OpenEventStreamOptions,
): () => void {
  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    return () => {};
  }

  let closed = false;
  let source: EventSource | null = null;
  let retry = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastSeq = opts.sinceSeq ?? 0;

  const url = () => {
    const u = new URL(baseUrl);
    u.searchParams.set("since_seq", String(lastSeq));
    return u.toString();
  };

  const handle = (ev: MessageEvent) => {
    try {
      const event = JSON.parse(ev.data) as WorkflowEvent;
      if (typeof event.seq === "number") {
        lastSeq = Math.max(lastSeq, event.seq);
      }
      opts.onEvent(event);
    } catch {
      // Ignore malformed frames (e.g. truncated during a drop).
    }
  };

  const connect = () => {
    if (closed) return;
    source = new EventSource(url());
    source.onopen = () => {
      retry = 0;
      opts.onOpen?.();
    };
    for (const kind of EVENT_KINDS) {
      source.addEventListener(kind, handle as EventListener);
    }
    source.onerror = (err) => {
      if (closed) return;
      opts.onError?.(err);
      source?.close();
      source = null;
      const delay = Math.min(1000 * 2 ** retry, MAX_BACKOFF_MS);
      retry += 1;
      timer = setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    source?.close();
    source = null;
  };
}
