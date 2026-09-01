"use client";

import { FileText, Loader2, Play, RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { RunFailedCard } from "@/components/workflow/run-failed-card";
import { useElapsed } from "@/hooks/use-elapsed";
import type { RunView } from "@/hooks/use-run-state";
import { WORKFLOW_NODES } from "@/lib/workflow-graph";
import { formatDuration } from "@/lib/format";
import { toApiError } from "@/lib/api-error";
import {
  useResumeRunMutation,
  useStartRunMutation,
} from "@/services/runs";

const TOTAL_NODES = WORKFLOW_NODES.length;

export function RunControlPanel({
  sessionId,
  view,
  hasRun,
  onRunStarted,
  onViewReport,
}: {
  sessionId: string;
  view: RunView;
  hasRun: boolean;
  onRunStarted: (runId: string) => void;
  onViewReport: () => void;
}) {
  const [startRun, start] = useStartRunMutation();
  const [resumeRun, resume] = useResumeRunMutation();
  const busy = start.isLoading || resume.isLoading;

  const status = hasRun ? view.overall.status : "idle";
  const running = status === "running";
  const elapsed = useElapsed(view.overall.startedAt, running);
  const doneCount = WORKFLOW_NODES.filter(
    (n) => view.nodes[n.name].status === "done",
  ).length;

  async function handleStart() {
    try {
      const res = await startRun(sessionId).unwrap();
      onRunStarted(res.runId);
    } catch (err) {
      toast.error(toApiError(err).message);
    }
  }

  async function handleResume() {
    try {
      const res = await resumeRun(sessionId).unwrap();
      onRunStarted(res.runId);
    } catch (err) {
      toast.error(toApiError(err).message);
    }
  }

  if (status === "idle") {
    return (
      <Button onClick={handleStart} disabled={busy} className="w-full">
        {busy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Play className="size-4" aria-hidden />
        )}
        Run research
      </Button>
    );
  }

  if (running) {
    const pct = Math.round((doneCount / TOTAL_NODES) * 100);
    return (
      <div className="flex flex-col gap-3">
        <Button disabled className="w-full">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Researching…
        </Button>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs font-medium">
            <span className="text-foreground tabular-nums">
              {doneCount} / {TOTAL_NODES} stages
            </span>
            <span className="text-muted-foreground tabular-nums">{pct}%</span>
          </div>
          <Progress value={pct} />
        </div>
        <p className="text-muted-foreground text-center text-xs tabular-nums">
          Elapsed {formatDuration(elapsed)}
        </p>
      </div>
    );
  }

  if (status === "failed") {
    // Resume re-runs from the last checkpoint, which only helps if the cause
    // could pass on a second attempt. For a rejected API key or a tripped cost
    // cap it cannot, and offering the button promises a recovery that isn't
    // available. Older runs predate the flag and default to allowing it.
    const canResume = view.error?.retryable !== false;
    return (
      <RunFailedCard error={view.error}>
        {canResume && (
          <Button size="sm" onClick={handleResume} disabled={busy}>
            <RotateCcw className="size-4" aria-hidden />
            Resume
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={handleStart}
          disabled={busy}
        >
          <RefreshCw className="size-4" aria-hidden />
          Start over
        </Button>
      </RunFailedCard>
    );
  }

  // completed
  return (
    <div className="flex flex-col gap-2">
      <Button onClick={onViewReport} className="w-full">
        <FileText className="size-4" aria-hidden />
        View report
      </Button>

      {view.overall.durationMs !== undefined && (
        <p className="text-muted-foreground text-center text-xs tabular-nums">
          Completed in {formatDuration(view.overall.durationMs)}
        </p>
      )}
    </div>
  );
}
