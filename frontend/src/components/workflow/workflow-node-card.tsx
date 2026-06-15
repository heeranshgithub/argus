"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { NodeStatusBadge } from "@/components/workflow/node-status-badge";
import { NodeOutput } from "@/components/workflow/outputs/node-output";
import { useElapsed } from "@/hooks/use-elapsed";
import type { NodeView } from "@/hooks/use-run-state";
import { type NodeMeta } from "@/lib/workflow-graph";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

export function WorkflowNodeCard({
  meta,
  node,
  isLast,
  nextRunning,
  onViewReport,
}: {
  meta: NodeMeta;
  node: NodeView;
  isLast: boolean;
  nextRunning: boolean;
  onViewReport?: () => void;
}) {
  const Icon = meta.icon;
  const running = node.status === "running";
  const failed = node.status === "failed";
  const hasDetail = node.status !== "pending";
  const [open, setOpen] = useState(running || failed);

  const liveMs = useElapsed(node.startedAt, running);
  const duration =
    node.durationMs !== undefined
      ? formatDuration(node.durationMs)
      : running
        ? formatDuration(liveMs)
        : null;

  return (
    <li className="flex gap-4">
      {/* Left rail: status dot + connector line */}
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full border",
            running &&
              "border-blue-500/40 bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
            node.status === "done" &&
              "border-emerald-500/40 bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
            failed &&
              "border-red-500/40 bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
            node.status === "pending" && "bg-muted text-muted-foreground",
          )}
        >
          <Icon className="size-4" aria-hidden />
        </span>
        {!isLast && (
          <span
            aria-hidden
            className={cn(
              "mt-1 w-px flex-1 bg-border",
              nextRunning &&
                "animate-pulse bg-blue-400 motion-reduce:animate-none",
            )}
          />
        )}
      </div>

      {/* Right: content card */}
      <div className="mb-4 flex-1 rounded-lg border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-medium">{meta.label}</h3>
          {node.iterations > 1 && (
            <Badge variant="outline" className="text-xs">
              iteration {node.iterations}
            </Badge>
          )}
          <div className="ml-auto flex items-center gap-2">
            {duration && (
              <span className="text-muted-foreground text-xs tabular-nums">
                {duration}
              </span>
            )}
            <NodeStatusBadge status={node.status} />
          </div>
        </div>

        <p className="text-muted-foreground mt-1 text-sm">{meta.description}</p>

        {/* Screen-reader status announcements, one per status change. */}
        <span className="sr-only" aria-live="polite">
          {meta.label} {node.status}
        </span>

        {failed && node.error && (
          <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {node.error.message}
          </p>
        )}

        {hasDetail && (
          <Collapsible open={open} onOpenChange={setOpen} className="mt-3">
            <CollapsibleTrigger className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 rounded">
              <ChevronDown
                className={cn(
                  "size-3.5 transition-transform",
                  open && "rotate-180",
                )}
                aria-hidden
              />
              {open ? "Hide details" : "Show details"}
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-3">
              <NodeOutput
                name={meta.name}
                node={node}
                onViewReport={onViewReport}
              />
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </li>
  );
}
