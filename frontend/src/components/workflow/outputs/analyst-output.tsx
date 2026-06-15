import { StatChip } from "@/components/workflow/outputs/stat-chip";
import { num } from "@/components/workflow/outputs/stat";
import type { NodeView } from "@/hooks/use-run-state";

export function AnalystOutput({ node }: { node: NodeView }) {
  const chars = num(node.output, "overview_chars");

  if (chars === undefined) {
    return (
      <p className="text-muted-foreground text-sm">
        Synthesizing the overview, products, customers, and risks…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <StatChip label="overview characters" value={chars.toLocaleString()} />
      </div>
      <p className="text-muted-foreground text-xs">
        The full analysis appears in the report once the run completes.
      </p>
    </div>
  );
}
