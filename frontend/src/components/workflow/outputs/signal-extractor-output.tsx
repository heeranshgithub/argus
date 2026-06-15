import { StatChip } from "@/components/workflow/outputs/stat-chip";
import { num } from "@/components/workflow/outputs/stat";
import type { NodeView } from "@/hooks/use-run-state";

export function SignalExtractorOutput({ node }: { node: NodeView }) {
  const signals = num(node.output, "signals");

  if (signals === undefined) {
    return (
      <p className="text-muted-foreground text-sm">
        Extracting business signals from the sources…
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      <StatChip label="signals extracted" value={signals} tone="good" />
    </div>
  );
}
