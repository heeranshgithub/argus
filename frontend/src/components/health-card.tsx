"use client";

import { useEffect } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useGetHealthQuery } from "@/services/health";

function StatusRow({ label, value }: { label: string; value: "ok" | "down" }) {
  const ok = value === "ok";
  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-sm font-medium",
          ok ? "text-emerald-600" : "text-destructive",
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
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Backend health</CardTitle>
        <CardDescription>
          Live status from <code>/api/health</code> via RTK Query.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading ? (
          <>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </>
        ) : error ? (
          <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="size-4" />
            Backend unreachable.
          </div>
        ) : data ? (
          <>
            <StatusRow label="API" value={data.status} />
            <StatusRow label="MongoDB" value={data.mongo} />
            <p className="text-xs text-muted-foreground">
              version {data.version}
            </p>
          </>
        ) : null}

        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          className="self-start"
        >
          <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
          Refresh
        </Button>
      </CardContent>
    </Card>
  );
}
