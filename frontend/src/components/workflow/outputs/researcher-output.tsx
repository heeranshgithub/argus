import { StatChip } from "@/components/workflow/outputs/stat-chip";
import { num } from "@/components/workflow/outputs/stat";
import type { NodeView } from "@/hooks/use-run-state";

export function ResearcherOutput({ node }: { node: NodeView }) {
  const sources = num(node.output, "new_sources");
  const questions = num(node.output, "questions_researched");

  if (sources === undefined && questions === undefined) {
    return (
      <p className="text-muted-foreground text-sm">
        Searching the web and fetching sources…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {sources !== undefined && (
          <StatChip label="new sources" value={sources} tone="good" />
        )}
        {questions !== undefined && (
          <StatChip label="questions researched" value={questions} />
        )}
      </div>
      {node.iterations > 1 && (
        <p className="text-muted-foreground text-xs">
          Iteration {node.iterations} — re-researching after the quality check
          asked for more depth.
        </p>
      )}
    </div>
  );
}
