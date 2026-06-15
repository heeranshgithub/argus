import { AlertTriangle } from "lucide-react";

import type { WorkflowError } from "@/types/workflow";

export function RunFailedCard({
  error,
  children,
}: {
  error: WorkflowError | null;
  children?: React.ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="mt-0.5 size-5 shrink-0 text-destructive"
          aria-hidden
        />
        <div className="flex flex-col gap-0.5">
          <p className="font-medium text-destructive">Run failed</p>
          <p className="text-sm text-destructive/90">
            {error?.message ?? "The workflow stopped unexpectedly."}
          </p>
          {error?.code && (
            <p className="text-xs text-destructive/70">Code: {error.code}</p>
          )}
        </div>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}
