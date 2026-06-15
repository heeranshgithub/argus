import { AnalystOutput } from "@/components/workflow/outputs/analyst-output";
import { PlannerOutput } from "@/components/workflow/outputs/planner-output";
import { QualityCheckOutput } from "@/components/workflow/outputs/quality-check-output";
import { ReporterOutput } from "@/components/workflow/outputs/reporter-output";
import { ResearcherOutput } from "@/components/workflow/outputs/researcher-output";
import { SignalExtractorOutput } from "@/components/workflow/outputs/signal-extractor-output";
import type { NodeView } from "@/hooks/use-run-state";
import type { NodeName } from "@/types/workflow";

/** Render the node-specific output preview for a given node. */
export function NodeOutput({
  name,
  node,
  onViewReport,
}: {
  name: NodeName;
  node: NodeView;
  onViewReport?: () => void;
}) {
  switch (name) {
    case "planner":
      return <PlannerOutput node={node} />;
    case "researcher":
      return <ResearcherOutput node={node} />;
    case "signal_extractor":
      return <SignalExtractorOutput node={node} />;
    case "analyst":
      return <AnalystOutput node={node} />;
    case "quality_check":
      return <QualityCheckOutput node={node} />;
    case "reporter":
      return <ReporterOutput node={node} onViewReport={onViewReport} />;
  }
}
