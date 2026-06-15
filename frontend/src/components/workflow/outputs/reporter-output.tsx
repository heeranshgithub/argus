import { FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatChip } from "@/components/workflow/outputs/stat-chip";
import { num } from "@/components/workflow/outputs/stat";
import type { NodeView } from "@/hooks/use-run-state";

export function ReporterOutput({
  node,
  onViewReport,
}: {
  node: NodeView;
  onViewReport?: () => void;
}) {
  const sections = num(node.output, "sections");
  const sources = num(node.output, "sources");
  const done = node.status === "done";

  if (!done && sections === undefined) {
    return (
      <p className="text-muted-foreground text-sm">
        Assembling the final report…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {sections !== undefined && (
          <StatChip label="sections" value={sections} tone="good" />
        )}
        {sources !== undefined && (
          <StatChip label="sources cited" value={sources} />
        )}
      </div>
      {done && onViewReport && (
        <Button size="sm" className="w-fit" onClick={onViewReport}>
          <FileText className="size-4" aria-hidden />
          View report
        </Button>
      )}
    </div>
  );
}
