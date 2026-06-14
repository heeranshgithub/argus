import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/types/session";

/**
 * Maps a status to a colored badge. Kept generic (gray/blue/green/red) so it can
 * be reused for workflow-run states in later parts.
 */
const STATUS_STYLES: Record<SessionStatus, { label: string; className: string }> = {
  created: {
    label: "Created",
    className: "bg-muted text-muted-foreground",
  },
  running: {
    label: "Running",
    className: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  },
  completed: {
    label: "Completed",
    className:
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: SessionStatus;
  className?: string;
}) {
  const { label, className: styles } = STATUS_STYLES[status];
  return (
    <Badge variant="secondary" className={cn(styles, className)}>
      {label}
    </Badge>
  );
}
