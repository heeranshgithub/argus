"use client";

import { useEffect } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useGetHealthQuery } from "@/services/health";

function StatusRow({ label, value }: { label: string; value: "ok" | "down" }) {
  const ok = value === "ok";
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background/60 px-3 py-2.5">
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-sm font-semibold",
          ok ? "text-primary" : "text-destructive",
        )}
      >
        {ok ? (
          <CheckCircle2 className="size-4" />
        ) : (
          <XCircle className="size-4" />
        )}
        {value}
      </span>
    </div>
  );
}

/**
 * Live backend health, rendered chrome-free so it can sit inside the home
 * status panel. The surrounding panel supplies the heading and border.
 */
export function HealthCard() {
  const { data, error, isLoading, isFetching, refetch } = useGetHealthQuery();

  useEffect(() => {
    if (error) {
      toast.error("Could not reach the backend", {
        description: "Is the API running on the configured base URL?",
      });
    }
  }, [error]);

  return (
    <div className="flex flex-col gap-3">
      {isLoading ? (
        <>
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
          <AlertCircle className="size-4" />
          Backend unreachable.
        </div>
      ) : data ? (
        <>
          <StatusRow label="API" value={data.status} />
          <StatusRow label="MongoDB" value={data.mongo} />
        </>
      ) : null}

      <div className="flex items-center justify-between pt-1">
        <p className="font-mono text-xs text-muted-foreground">
          {data ? `v${data.version}` : "Live · /api/health"}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
          Refresh
        </Button>
      </div>
    </div>
  );
}
