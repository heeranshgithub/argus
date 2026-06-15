/**
 * Workflow run wire types — mirror the backend's `WorkflowRunOut` /
 * `WorkflowEventOut` (see backend `app/models/workflow.py`).
 *
 * Naming caveat: the backend's camelCase bridge renames model *fields*
 * (`startedAt`, `nodeStatus`) but NOT enum string *values*, dict *keys*, or
 * free-form `payload` contents. So `kind`, the `node` value, the `nodeStatus`
 * keys, and `payload` keys all arrive snake_case — and these types reflect that
 * reality rather than the idealized camelCase sketch in the plan.
 */

/** Canonical graph node names, in execution order (snake_case on the wire). */
export type NodeName =
  | "planner"
  | "researcher"
  | "signal_extractor"
  | "analyst"
  | "quality_check"
  | "reporter";

/** Sentinel `node` value for run-level events (start/complete/fail). */
export const RUN_NODE = "__run__" as const;

export type NodeStatus = "pending" | "running" | "done" | "failed";

export type EventKind =
  | "run_started"
  | "run_completed"
  | "run_failed"
  | "node_started"
  | "node_finished"
  | "node_errored"
  | "node_output";

export type RunStatus = "running" | "completed" | "failed";

export interface WorkflowError {
  code: string;
  message: string;
  traceback?: string | null;
}

export interface WorkflowEvent {
  runId: string;
  sessionId: string;
  /** A `NodeName` for node events, or `"__run__"` for run-level events. */
  node: NodeName | typeof RUN_NODE;
  kind: EventKind;
  payload: Record<string, unknown>;
  ts: string; // ISO 8601
  seq: number;
}

export interface WorkflowRun {
  id: string;
  sessionId: string;
  status: RunStatus;
  startedAt: string;
  finishedAt: string | null;
  nodeStatus: Record<string, NodeStatus>;
  events: WorkflowEvent[];
  error: WorkflowError | null;
  finalStateKeys: string[];
}

export interface WorkflowRunSummary {
  id: string;
  sessionId: string;
  status: RunStatus;
  startedAt: string;
  finishedAt: string | null;
  nodeStatus: Record<string, NodeStatus>;
  error: WorkflowError | null;
}

export interface RunListResponse {
  items: WorkflowRunSummary[];
  total: number;
}

export interface RunAccepted {
  runId: string;
  status: RunStatus;
}
