/**
 * Static metadata for the six workflow nodes: canonical order, labels, icons,
 * and one-line descriptions. Kept separate from live data so the progress
 * timeline can render its full shape before any event arrives.
 */

import {
  BrainCog,
  Compass,
  FileText,
  Search,
  ShieldCheck,
  Signpost,
  type LucideIcon,
} from "lucide-react";

import type { NodeName } from "@/types/workflow";

export interface NodeMeta {
  name: NodeName;
  label: string;
  description: string;
  icon: LucideIcon;
}

/** The six nodes in canonical execution order. */
export const WORKFLOW_NODES: readonly NodeMeta[] = [
  {
    name: "planner",
    label: "Planner",
    description: "Breaks the objective into focused research sub-questions.",
    icon: Compass,
  },
  {
    name: "researcher",
    label: "Researcher",
    description: "Searches the web and gathers source material.",
    icon: Search,
  },
  {
    name: "signal_extractor",
    label: "Signal Extractor",
    description: "Pulls business signals from the gathered sources.",
    icon: Signpost,
  },
  {
    name: "analyst",
    label: "Analyst",
    description: "Synthesizes an overview, products, customers, and risks.",
    icon: BrainCog,
  },
  {
    name: "quality_check",
    label: "Quality Check",
    description: "Scores coverage and decides whether to research again.",
    icon: ShieldCheck,
  },
  {
    name: "reporter",
    label: "Reporter",
    description: "Assembles the final nine-section research report.",
    icon: FileText,
  },
] as const;

export const NODE_ORDER: readonly NodeName[] = WORKFLOW_NODES.map((n) => n.name);

const NODE_META_BY_NAME = new Map<NodeName, NodeMeta>(
  WORKFLOW_NODES.map((n) => [n.name, n]),
);

export function nodeMeta(name: NodeName): NodeMeta {
  const meta = NODE_META_BY_NAME.get(name);
  if (!meta) throw new Error(`Unknown workflow node: ${name}`);
  return meta;
}

/** Human-friendly label for a node name, tolerant of unknown values. */
export function nodeLabel(name: string): string {
  return NODE_META_BY_NAME.get(name as NodeName)?.label ?? name;
}
