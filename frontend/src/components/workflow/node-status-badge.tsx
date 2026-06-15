import { Check, Clock, Loader2, X, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { NodeStatus } from "@/types/workflow";

/**
 * Status pill for a workflow node. Color is never the only signal — each status
 * also carries a distinct icon (and the running state animates), so the state is
 * legible to color-blind users and in high-contrast modes.
 */
const STATUS: Record<
  NodeStatus,
  { label: string; className: string; icon: LucideIcon; spin?: boolean }
> = {
  pending: {
    label: "Pending",
    className: "bg-muted text-muted-foreground",
    icon: Clock,
  },
  running: {
    label: "Running",
    className:
      "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
    icon: Loader2,
    spin: true,
  },
  done: {
    label: "Done",
    className: "bg-primary/15 text-primary dark:bg-primary/20",
    icon: Check,
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    icon: X,
  },
};

export function NodeStatusBadge({
  status,
  className,
}: {
  status: NodeStatus;
  className?: string;
}) {
  const { label, className: styles, icon: Icon, spin } = STATUS[status];
  return (
    <Badge
      variant="secondary"
      className={cn(styles, className)}
      aria-label={`Status: ${label}`}
    >
      <Icon className={cn("size-3", spin && "animate-spin")} aria-hidden />
      {label}
    </Badge>
  );
}
