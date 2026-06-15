"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getLastRequestId } from "@/lib/request-id";

/**
 * Friendly recovery UI shared by the App Router `error.tsx` boundaries
 * (PLAN_PART_5 §2.2). Shows a Reload action and the last request id for support.
 */
export function ErrorState({
  title = "Something went wrong",
  description = "An unexpected error occurred. You can try again.",
  reset,
  error,
}: {
  title?: string;
  description?: string;
  reset: () => void;
  error?: Error & { digest?: string };
}) {
  useEffect(() => {
    if (error) console.error(error);
  }, [error]);

  const requestId = getLastRequestId();

  return (
    <div
      role="alert"
      className="mx-auto flex max-w-md flex-col items-center gap-4 py-20 text-center"
    >
      <AlertTriangle className="size-10 text-destructive" aria-hidden />
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      <Button onClick={reset}>Reload</Button>
      {(requestId || error?.digest) && (
        <p className="text-muted-foreground font-mono text-xs">
          Reference: {error?.digest ?? requestId}
        </p>
      )}
    </div>
  );
}
