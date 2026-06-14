import Link from "next/link";

import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatRelative } from "@/lib/format";
import type { Session } from "@/types/session";

export function SessionListItem({ session }: { session: Session }) {
  return (
    <Link href={`/sessions/${session.id}`} className="block">
      <Card className="flex-row items-center justify-between gap-4 p-4 transition-colors hover:bg-accent/50">
        <div className="min-w-0 flex flex-col gap-1">
          <span className="truncate font-medium">{session.companyName}</span>
          <span className="truncate text-sm text-muted-foreground">
            {session.objective}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <StatusBadge status={session.status} />
          <span className="text-xs text-muted-foreground">
            {formatRelative(session.createdAt)}
          </span>
        </div>
      </Card>
    </Link>
  );
}
