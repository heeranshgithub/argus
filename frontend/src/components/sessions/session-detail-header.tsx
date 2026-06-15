import { CalendarDays, ExternalLink, Globe, Target } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { formatRelative } from "@/lib/format";
import type { Session } from "@/types/session";

function domainOf(website: string): string {
  try {
    return new URL(website).hostname.replace(/^www\./, "");
  } catch {
    return website.replace(/^https?:\/\//, "").replace(/^www\./, "");
  }
}

export function SessionDetailHeader({ session }: { session: Session }) {
  const initial = session.companyName.trim().charAt(0).toUpperCase() || "?";

  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      {/* faint brand wash */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-primary/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute right-6 top-1/2 hidden -translate-y-1/2 select-none font-display text-[10rem] font-black leading-none text-primary/[0.05] sm:block dark:text-primary/[0.07]"
      >
        /
      </div>

      <div className="relative flex flex-col gap-5 p-6 sm:p-7">
        <div className="flex flex-wrap items-start gap-4">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-primary text-2xl font-extrabold text-primary-foreground shadow-sm font-display">
            {initial}
          </span>
          <div className="flex min-w-0 flex-col gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-3xl font-extrabold tracking-tight">
                {session.companyName}
              </h1>
              <StatusBadge status={session.status} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={session.website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                <Globe className="size-3.5" />
                {domainOf(session.website)}
                <ExternalLink className="size-3 opacity-60" />
              </a>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                <CalendarDays className="size-3.5" />
                Created {formatRelative(session.createdAt)}
              </span>
            </div>
          </div>
        </div>

        {/* Objective, called out as the brief. */}
        <div className="flex gap-3 rounded-xl border border-border bg-background/50 p-4">
          <Target className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Objective
            </span>
            <p className="max-w-2xl text-sm leading-relaxed text-foreground/90">
              {session.objective}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
