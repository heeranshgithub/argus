import { StatChip } from "@/components/workflow/outputs/stat-chip";
import { num } from "@/components/workflow/outputs/stat";
import type { NodeView } from "@/hooks/use-run-state";

export function PlannerOutput({ node }: { node: NodeView }) {
  const added = num(node.output, "new_questions");
  const total = num(node.output, "total");

  if (added === undefined && total === undefined) {
    return <Pending />;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {added !== undefined && (
        <StatChip label="new sub-questions" value={added} />
      )}
      {total !== undefined && (
        <StatChip label="questions in plan" value={total} />
      )}
    </div>
  );
}

function Pending() {
  return (
    <p className="text-muted-foreground text-sm">Planning sub-questions…</p>
  );
}
