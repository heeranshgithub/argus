/**
 * Pure derivation of a render-ready view model from a run's event list.
 *
 * The reducer is deliberately side-effect free and exported on its own so it can
 * be unit-tested with synthetic event arrays (PLAN_PART_4 §7.2). It tolerates
 * out-of-order and duplicate events: callers de-duplicate by `seq`, and the
 * fold here is order-independent for terminal status because later events win.
 */

import { NODE_ORDER } from "@/lib/workflow-graph";
import type {
  NodeName,
  NodeStatus,
  RunStatus,
  WorkflowError,
  WorkflowEvent,
} from "@/types/workflow";

export interface NodeView {
  status: NodeStatus;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  /** Merged `node_output` + `node_finished` payload (preview fields). */
  output: Record<string, unknown>;
  error?: WorkflowError;
  /** How many times this node has started (loop-back shows iteration ≥ 2). */
  iterations: number;
}

export interface RunView {
  nodes: Record<NodeName, NodeView>;
  overall: {
    status: RunStatus;
    startedAt?: string;
    finishedAt?: string;
    durationMs?: number;
  };
  /** The node currently `running`, if any (drives the connector pulse). */
  activeNode: NodeName | null;
  error: WorkflowError | null;
  lastSeq: number;
}

const NODE_SET = new Set<string>(NODE_ORDER);

function isNodeName(node: string): node is NodeName {
  return NODE_SET.has(node);
}

function emptyNodes(): Record<NodeName, NodeView> {
  return Object.fromEntries(
    NODE_ORDER.map((name) => [
      name,
      { status: "pending" as NodeStatus, output: {}, iterations: 0 },
    ]),
  ) as Record<NodeName, NodeView>;
}

function durationBetween(start?: string, end?: string): number | undefined {
  if (!start || !end) return undefined;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Number.isFinite(ms) && ms >= 0 ? ms : undefined;
}

/** The persisted run record, used as the authority on terminal state. */
export interface RunSeed {
  status: RunStatus;
  startedAt?: string;
  finishedAt?: string | null;
  error?: WorkflowError | null;
}

/** Fold a run's events into a `RunView`.
 *
 * `seed` is the persisted run record and outranks the event stream for terminal
 * state. Events alone are not sufficient: a run can reach `failed` in the
 * database without a `run_failed` event ever being emitted — that is exactly
 * what happened when the failure handler itself threw — and a view derived only
 * from events would then show "Researching…" forever. Node progress still comes
 * from events; only the overall verdict is seeded.
 */
export function deriveRunView(
  events: readonly WorkflowEvent[],
  seed?: RunSeed,
): RunView {
  const view: RunView = {
    nodes: emptyNodes(),
    overall: { status: "running" },
    activeNode: null,
    error: null,
    lastSeq: 0,
  };

  if (seed) {
    view.overall.status = seed.status;
    view.overall.startedAt = seed.startedAt;
    if (seed.finishedAt) view.overall.finishedAt = seed.finishedAt;
    if (seed.error) view.error = seed.error;
  }

  const ordered = [...events].sort((a, b) => a.seq - b.seq);

  for (const event of ordered) {
    view.lastSeq = Math.max(view.lastSeq, event.seq);
    const { node, payload, ts, kind } = event;

    switch (kind) {
      case "run_started":
        view.overall.startedAt = ts;
        break;
      case "run_completed":
        view.overall.status = "completed";
        view.overall.finishedAt = ts;
        break;
      case "run_failed":
        view.overall.status = "failed";
        view.overall.finishedAt = ts;
        view.error = {
          code: String(payload.code ?? "workflow_failed"),
          message: String(payload.message ?? "The run failed."),
        };
        break;
      default:
        if (!isNodeName(node)) break;
        applyNodeEvent(view.nodes[node], kind, payload, ts);
    }
  }

  view.overall.durationMs = durationBetween(
    view.overall.startedAt,
    view.overall.finishedAt,
  );

  if (view.overall.status === "running") {
    view.activeNode =
      NODE_ORDER.find((name) => view.nodes[name].status === "running") ?? null;
  } else {
    // The run is over, so nothing is in flight. A node can be left `running`
    // when the run ended without its `node_finished` event (a crash mid-node,
    // or a terminal state known only from the seed); leaving it that way spins
    // a progress indicator forever.
    view.activeNode = null;
    for (const name of NODE_ORDER) {
      if (view.nodes[name].status === "running") {
        view.nodes[name].status =
          view.overall.status === "failed" ? "failed" : "done";
        view.nodes[name].finishedAt ??= view.overall.finishedAt;
      }
    }
  }

  return view;
}

function applyNodeEvent(
  nv: NodeView,
  kind: WorkflowEvent["kind"],
  payload: Record<string, unknown>,
  ts: string,
): void {
  switch (kind) {
    case "node_started":
      nv.status = "running";
      nv.startedAt = ts;
      nv.finishedAt = undefined;
      nv.durationMs = undefined;
      nv.error = undefined;
      nv.iterations += 1;
      break;
    case "node_output":
      nv.output = { ...nv.output, ...payload };
      break;
    case "node_finished": {
      const { duration_ms: durationMs, ...rest } = payload;
      nv.status = "done";
      nv.finishedAt = ts;
      nv.durationMs =
        typeof durationMs === "number"
          ? durationMs
          : durationBetween(nv.startedAt, ts);
      nv.output = { ...nv.output, ...rest };
      break;
    }
    case "node_errored":
      nv.status = "failed";
      nv.finishedAt = ts;
      nv.error = {
        code: String(payload.type ?? "node_error"),
        message: String(payload.error ?? "This step failed."),
        traceback:
          typeof payload.traceback === "string" ? payload.traceback : null,
      };
      break;
  }
}
