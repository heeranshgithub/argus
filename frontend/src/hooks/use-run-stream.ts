/**
 * Live run timeline: seed from the persisted run (`getRun`), then attach the SSE
 * stream from the last seeded `seq`. Backfill + live events are merged into one
 * de-duplicated map keyed by `seq`, so a mid-run refresh rebuilds the exact UI
 * state in one round-trip and continues live with no missed or duplicate events.
 */

"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";

import { env } from "@/lib/env";
import { openEventStream } from "@/lib/sse";
import { deriveRunView, type RunView } from "@/hooks/use-run-state";
import { runsApi, useGetRunQuery } from "@/services/runs";
import { useAppDispatch } from "@/store/hooks";
import type { WorkflowEvent } from "@/types/workflow";

interface State {
  bySeq: Map<number, WorkflowEvent>;
  /** The runId these events belong to (guards against stale resets). */
  runId: string | null;
}

type Action =
  | { type: "seed"; runId: string; events: WorkflowEvent[] }
  | { type: "append"; event: WorkflowEvent }
  | { type: "clear" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "seed": {
      const bySeq = new Map<number, WorkflowEvent>();
      for (const e of action.events) bySeq.set(e.seq, e);
      return { bySeq, runId: action.runId };
    }
    case "append": {
      if (state.bySeq.has(action.event.seq)) return state;
      const bySeq = new Map(state.bySeq);
      bySeq.set(action.event.seq, action.event);
      return { ...state, bySeq };
    }
    case "clear":
      return { bySeq: new Map(), runId: null };
  }
}

export interface UseRunStreamResult {
  view: RunView;
  events: WorkflowEvent[];
  status: RunView["overall"]["status"];
  error: RunView["error"];
  lastSeq: number;
  isStreaming: boolean;
  isSeeding: boolean;
  /** True after an SSE drop while the wrapper retries (drives the "lost" pill). */
  isReconnecting: boolean;
}

const TERMINAL = new Set(["run_completed", "run_failed"]);

export function useRunStream(
  sessionId: string,
  runId: string | null | undefined,
): UseRunStreamResult {
  const dispatch = useAppDispatch();
  const [state, send] = useReducer(reducer, { bySeq: new Map(), runId: null });
  const [isReconnecting, setReconnecting] = useState(false);

  const {
    data: seed,
    isFetching: isSeeding,
  } = useGetRunQuery(
    { sessionId, runId: runId ?? "" },
    { skip: !runId },
  );

  // Seed once per runId from the persisted snapshot. `state.runId` records which
  // run the merged events belong to, so we can detect "already seeded" without a
  // render-time ref.
  const seeded = runId != null && state.runId === runId;
  useEffect(() => {
    if (!runId) {
      if (state.runId !== null) send({ type: "clear" });
      return;
    }
    if (seed && seed.id === runId && state.runId !== runId) {
      send({ type: "seed", runId, events: seed.events });
    }
  }, [runId, seed, state.runId]);

  // Derive the view model from the merged event set.
  const events = useMemo(
    () => [...state.bySeq.values()].sort((a, b) => a.seq - b.seq),
    [state.bySeq],
  );
  const view = useMemo(() => deriveRunView(events), [events]);

  // Mirror the latest seq into a ref (in an effect, never during render) so the
  // stream can open at the right resume point without depending on every tick.
  const lastSeqRef = useRef(0);
  useEffect(() => {
    lastSeqRef.current = view.lastSeq;
  }, [view.lastSeq]);

  const isTerminal = view.overall.status !== "running";
  const seedStatus = seed?.id === runId ? seed?.status : undefined;
  // We hold an open stream whenever the run is seeded and not yet finished.
  const isStreaming =
    seeded && !isTerminal && (seedStatus === undefined || seedStatus === "running");

  // Attach the live stream once seeded, unless the run already finished.
  useEffect(() => {
    if (!runId || !seeded) return;
    if (seedStatus && seedStatus !== "running") return;

    const url = `${env.NEXT_PUBLIC_API_BASE_URL}/api/sessions/${sessionId}/runs/${runId}/events`;
    const close = openEventStream(url, {
      sinceSeq: lastSeqRef.current,
      onOpen: () => setReconnecting(false),
      onError: () => setReconnecting(true),
      onEvent: (event) => {
        setReconnecting(false);
        send({ type: "append", event });
        if (TERMINAL.has(event.kind)) {
          // A finished run produces a report and flips session status.
          dispatch(
            runsApi.util.invalidateTags([
              { type: "Report", id: sessionId },
              { type: "Run", id: runId },
              { type: "Run", id: "LIST" },
              { type: "Session", id: sessionId },
            ]),
          );
        }
      },
    });
    return () => {
      setReconnecting(false);
      close();
    };
  }, [sessionId, runId, seeded, seedStatus, dispatch]);

  return {
    view,
    events,
    status: view.overall.status,
    error: view.error,
    lastSeq: view.lastSeq,
    isStreaming,
    isSeeding,
    isReconnecting: isReconnecting && !isTerminal,
  };
}
