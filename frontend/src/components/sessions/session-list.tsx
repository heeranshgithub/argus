"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";

import { SessionEmptyState } from "@/components/sessions/session-empty-state";
import { SessionListItem } from "@/components/sessions/session-list-item";
import { Skeleton } from "@/components/ui/skeleton";
import { toApiError } from "@/lib/api-error";
import { useGetSessionsQuery } from "@/services/sessions";

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
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[76px] w-full" />
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

  return (
    <div className="flex flex-col gap-3">
      {data.items.map((session) => (
        <SessionListItem key={session.id} session={session} />
      ))}
    </div>
  );
}
