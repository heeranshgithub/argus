"use client";

import { Loader2, WifiOff } from "lucide-react";

import { RunFailedCard } from "@/components/workflow/run-failed-card";
import { WorkflowNodeCard } from "@/components/workflow/workflow-node-card";
import type { RunView } from "@/hooks/use-run-state";
import { WORKFLOW_NODES } from "@/lib/workflow-graph";

export function WorkflowProgress({
  view,
  isReconnecting,
  hasRun,
  onViewReport,
}: {
  view: RunView;
  isReconnecting: boolean;
  hasRun: boolean;
  onViewReport?: () => void;
}) {
  if (!hasRun) {
    return (
      <p className="text-muted-foreground rounded-lg border border-dashed py-12 text-center text-sm">
        No run yet. Start the research to watch each step here.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {isReconnecting && (
        <div
          role="status"
          className="flex items-center gap-2 self-start rounded-full border border-amber-500/30 bg-amber-500/5 px-3 py-1 text-xs text-amber-700 dark:text-amber-300"
        >
          <WifiOff className="size-3.5" aria-hidden />
          Connection lost — retrying…
        </div>
      )}

      {view.overall.status === "failed" && <RunFailedCard error={view.error} />}

      <ol className="mt-1">
        {WORKFLOW_NODES.map((meta, i) => {
          const next = WORKFLOW_NODES[i + 1];
          const nextRunning =
            next != null && view.nodes[next.name].status === "running";
          return (
            <WorkflowNodeCard
              key={meta.name}
              meta={meta}
              node={view.nodes[meta.name]}
              isLast={i === WORKFLOW_NODES.length - 1}
              nextRunning={nextRunning}
              onViewReport={onViewReport}
            />
          );
        })}
      </ol>

      {view.overall.status === "running" && (
        <p className="text-muted-foreground flex items-center gap-2 text-xs">
          <Loader2 className="size-3.5 animate-spin motion-reduce:hidden" aria-hidden />
          Streaming live updates…
        </p>
      )}
    </div>
  );
}
