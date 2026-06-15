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
    // Don't hammer reconnects while offline; recheck shortly (PLAN §2.2).
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      timer = setTimeout(connect, 2000);
      return;
    }
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

export interface ChatDelta {
  seq: number;
  text: string;
}

export interface ChatDone {
  messageId: string;
  status: "complete" | "failed";
  citations: import("@/types/chat").Citation[];
  error: { code: string; message: string } | null;
}

export interface OpenChatStreamOptions {
  onDelta: (delta: ChatDelta) => void;
  onDone: (done: ChatDone) => void;
  onOpen?: () => void;
  onError?: (err: unknown) => void;
  /** Resume point; only deltas with `seq > sinceSeq` are (re)delivered. */
  sinceSeq?: number;
}

/**
 * Open a resilient SSE stream for a chat reply (`event: delta` / `event: done`).
 *
 * Mirrors {@link openEventStream}'s `since_seq` resumability so a refresh
 * mid-generation replays only un-seen token deltas. The `done` frame ends the
 * stream (no reconnect after it). Returns an `unsubscribe()` that closes the
 * stream and cancels any pending reconnect; safe to call during SSR.
 */
export function openChatStream(
  baseUrl: string,
  opts: OpenChatStreamOptions,
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

  const close = () => {
    closed = true;
    if (timer) clearTimeout(timer);
    source?.close();
    source = null;
  };

  const onDelta = (ev: MessageEvent) => {
    try {
      const delta = JSON.parse(ev.data) as ChatDelta;
      if (typeof delta.seq === "number") lastSeq = Math.max(lastSeq, delta.seq);
      opts.onDelta(delta);
    } catch {
      // Ignore malformed frames.
    }
  };

  const onDone = (ev: MessageEvent) => {
    try {
      opts.onDone(JSON.parse(ev.data) as ChatDone);
    } catch {
      // Ignore malformed frames.
    }
    close();
  };

  const connect = () => {
    if (closed) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      timer = setTimeout(connect, 2000);
      return;
    }
    source = new EventSource(url());
    source.onopen = () => {
      retry = 0;
      opts.onOpen?.();
    };
    source.addEventListener("delta", onDelta as EventListener);
    source.addEventListener("done", onDone as EventListener);
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
  return close;
}
