import { ExternalLink } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { formatRelative } from "@/lib/format";
import type { Session } from "@/types/session";

export function SessionDetailHeader({ session }: { session: Session }) {
  return (
    <div className="flex flex-col gap-3 border-b pb-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          {session.companyName}
        </h1>
        <StatusBadge status={session.status} />
      </div>

      <a
        href={session.website}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
      >
        {session.website}
        <ExternalLink className="size-3.5" />
      </a>

      <p className="max-w-2xl text-sm text-foreground/90">{session.objective}</p>

      <p className="text-xs text-muted-foreground">
        Created {formatRelative(session.createdAt)}
      </p>
    </div>
  );
}
