"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { SessionDetailHeader } from "@/components/sessions/session-detail-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toApiError } from "@/lib/api-error";
import { useGetSessionQuery } from "@/services/sessions";

function PlaceholderPanel({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">Coming soon.</p>
      </CardContent>
    </Card>
  );
}

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
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <Link
        href="/sessions"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to sessions
      </Link>

      {isLoading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-28 w-full" />
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
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
        <div className="flex flex-col gap-6">
          <SessionDetailHeader session={data} />
          <div className="grid gap-4 md:grid-cols-2">
            <PlaceholderPanel title="Workflow" />
            <PlaceholderPanel title="Report" />
          </div>
        </div>
      ) : null}
    </main>
  );
}
