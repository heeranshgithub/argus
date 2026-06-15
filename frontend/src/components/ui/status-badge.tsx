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
    className:
      "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  },
  completed: {
    label: "Completed",
    className: "bg-primary/15 text-primary dark:bg-primary/20",
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
