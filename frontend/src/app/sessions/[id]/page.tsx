"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense } from "react";

import { SessionDetailHeader } from "@/components/sessions/session-detail-header";
import { SessionWorkspace } from "@/components/sessions/session-workspace";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toApiError } from "@/lib/api-error";
import { useGetSessionQuery } from "@/services/sessions";

function NotFoundView() {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed py-16 text-center">
      <div className="flex flex-col gap-1">
        <p className="font-medium">Session not found</p>
        <p className="text-sm text-muted-foreground">
          It may have been removed, or the link is incorrect.
        </p>
      </div>
      <Button asChild>
        <Link href="/sessions">Back to sessions</Link>
      </Button>
    </div>
  );
}

export default function SessionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { data, error, isLoading } = useGetSessionQuery(id, { skip: !id });

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <Link
        href="/sessions"
        className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to sessions
      </Link>

      {isLoading ? (
        <div className="flex flex-col gap-8">
          <Skeleton className="h-44 w-full rounded-2xl" />
          <div className="grid gap-8 lg:grid-cols-[20rem_1fr]">
            <Skeleton className="h-44 w-full rounded-2xl" />
            <Skeleton className="h-64 w-full rounded-2xl" />
          </div>
        </div>
      ) : error ? (
        toApiError(error).code === "session_not_found" ? (
          <NotFoundView />
        ) : (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Could not load this session. Please try again.
          </div>
        )
      ) : data ? (
        <div className="flex flex-col gap-8">
          <SessionDetailHeader session={data} />
          <Suspense fallback={<Skeleton className="h-64 w-full" />}>
            <SessionWorkspace session={data} />
          </Suspense>
        </div>
      ) : null}
    </main>
  );
}
