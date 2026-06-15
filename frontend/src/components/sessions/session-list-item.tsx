import { ArrowUpRight, Globe } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/ui/status-badge";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Session, SessionStatus } from "@/types/session";

// Left-rail accent so a session's state reads at a glance, before the badge.
const ACCENT: Record<SessionStatus, string> = {
  created: "bg-muted-foreground/40",
  running: "bg-amber-400",
  completed: "bg-primary",
  failed: "bg-destructive",
};

function domainOf(website: string): string {
  try {
    return new URL(website).hostname.replace(/^www\./, "");
  } catch {
    return website.replace(/^https?:\/\//, "").replace(/^www\./, "");
  }
}

export function SessionListItem({ session }: { session: Session }) {
  const initial = session.companyName.trim().charAt(0).toUpperCase() || "?";

  return (
    <Link
      href={`/sessions/${session.id}`}
      className="group relative flex overflow-hidden rounded-xl border border-border bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
    >
      {/* status accent rail */}
      <span className={cn("w-1.5 shrink-0", ACCENT[session.status])} />

      <div className="flex min-w-0 flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent font-display text-lg font-bold text-accent-foreground">
              {initial}
            </span>
            <div className="min-w-0">
              <h3 className="truncate font-display text-lg font-bold leading-tight tracking-tight">
                {session.companyName}
              </h3>
              <span className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                <Globe className="size-3 shrink-0" />
                {domainOf(session.website)}
              </span>
            </div>
          </div>
          <StatusBadge status={session.status} />
        </div>

        <p className="line-clamp-2 text-sm text-muted-foreground">
          {session.objective}
        </p>

        <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-3">
          <span className="text-xs text-muted-foreground">
            {formatRelative(session.createdAt)}
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary opacity-0 transition-opacity group-hover:opacity-100">
            Open
            <ArrowUpRight className="size-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}
