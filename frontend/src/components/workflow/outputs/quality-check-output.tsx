import { ArrowRight, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { num } from "@/components/workflow/outputs/stat";
import { cn } from "@/lib/utils";
import type { NodeView } from "@/hooks/use-run-state";

export function QualityCheckOutput({ node }: { node: NodeView }) {
  const coverage = num(node.output, "coverage");
  const confidence = num(node.output, "confidence");
  const needsMore = node.output["needs_more_research"];

  if (coverage === undefined && confidence === undefined) {
    return (
      <p className="text-muted-foreground text-sm">
        Scoring coverage and confidence…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {coverage !== undefined && (
        <ScoreBar label="Coverage" value={coverage} />
      )}
      {confidence !== undefined && (
        <ScoreBar label="Confidence" value={confidence} />
      )}
      {typeof needsMore === "boolean" && (
        <RouteBadge needsMore={needsMore} />
      )}
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{pct}%</span>
      </div>
      <Progress
        value={pct}
        aria-label={`${label}: ${pct} percent`}
        indicatorClassName={cn(
          pct >= 70
            ? "bg-emerald-500"
            : pct >= 40
              ? "bg-amber-500"
              : "bg-red-500",
        )}
      />
    </div>
  );
}

function RouteBadge({ needsMore }: { needsMore: boolean }) {
  return needsMore ? (
    <Badge
      variant="secondary"
      className="w-fit bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
    >
      <RefreshCw className="size-3" aria-hidden />
      Research again
    </Badge>
  ) : (
    <Badge
      variant="secondary"
      className="w-fit bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
    >
      <ArrowRight className="size-3" aria-hidden />
      Finalize report
    </Badge>
  );
}
