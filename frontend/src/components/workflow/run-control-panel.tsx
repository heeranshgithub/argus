"use client";

import { FileText, Loader2, Play, RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
    return (
      <div className="flex flex-col gap-2">
        <Button disabled className="w-full">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Running… ({doneCount} of {TOTAL_NODES} nodes)
        </Button>
        <p className="text-muted-foreground text-center text-xs tabular-nums">
          Elapsed {formatDuration(elapsed)}
        </p>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <RunFailedCard error={view.error}>
        <Button size="sm" onClick={handleResume} disabled={busy}>
          <RotateCcw className="size-4" aria-hidden />
          Resume
        </Button>
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
      <Button
        variant="outline"
        onClick={handleStart}
        disabled={busy}
        className="w-full"
      >
        {busy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <RefreshCw className="size-4" aria-hidden />
        )}
        Re-run
      </Button>
      {view.overall.durationMs !== undefined && (
        <p className="text-muted-foreground text-center text-xs tabular-nums">
          Completed in {formatDuration(view.overall.durationMs)}
        </p>
      )}
    </div>
  );
}
