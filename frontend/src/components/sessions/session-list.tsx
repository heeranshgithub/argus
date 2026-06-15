"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";

import { SessionEmptyState } from "@/components/sessions/session-empty-state";
import { SessionListItem } from "@/components/sessions/session-list-item";
import { Skeleton } from "@/components/ui/skeleton";
import { toApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { useGetSessionsQuery } from "@/services/sessions";
import type { SessionStatus } from "@/types/session";

export function SessionList() {
  const { data, error, isLoading } = useGetSessionsQuery();

  useEffect(() => {
    if (error) {
      const { message } = toApiError(error);
      toast.error("Could not load sessions", { description: message });
    }
  }, [error]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        <AlertCircle className="size-4" />
        Could not load sessions. Please try again.
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return <SessionEmptyState />;
  }

  const counts = data.items.reduce(
    (acc, s) => {
      acc[s.status] = (acc[s.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<SessionStatus, number>,
  );

  const stats = [
    { label: "Total", value: data.items.length, dot: "bg-foreground/40" },
    { label: "Completed", value: counts.completed ?? 0, dot: "bg-primary" },
    { label: "Running", value: counts.running ?? 0, dot: "bg-amber-400" },
    { label: "Failed", value: counts.failed ?? 0, dot: "bg-destructive" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-border bg-card/60 px-4 py-3"
          >
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              <span className={cn("size-1.5 rounded-full", s.dot)} />
              {s.label}
            </div>
            <div className="mt-1 font-display text-2xl font-extrabold tracking-tight">
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data.items.map((session) => (
          <SessionListItem key={session.id} session={session} />
        ))}
      </div>
    </div>
  );
}
