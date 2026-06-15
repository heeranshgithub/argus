"use client";

import { useCallback, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReportPanel } from "@/components/report/report-panel";
import { RunControlPanel } from "@/components/workflow/run-control-panel";
import { WorkflowProgress } from "@/components/workflow/workflow-progress";
import { useRunStream } from "@/hooks/use-run-stream";
import { useGetLatestRunQuery } from "@/services/runs";
import type { Session } from "@/types/session";

type TabKey = "progress" | "report" | "chat";
const TAB_KEYS: readonly TabKey[] = ["progress", "report", "chat"];

function asTab(value: string | null): TabKey | null {
  return value && (TAB_KEYS as readonly string[]).includes(value)
    ? (value as TabKey)
    : null;
}

export function SessionWorkspace({ session }: { session: Session }) {
  const sessionId = session.id;

  // Prefer an explicitly-started run; otherwise fall back to the latest run.
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const { data: latest, isLoading: latestLoading } =
    useGetLatestRunQuery(sessionId);
  const runId = activeRunId ?? latest?.id ?? null;
  const hasRun = Boolean(runId);

  const stream = useRunStream(sessionId, runId);

  // Tab state is URL-synced; with no explicit tab we follow the run status.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const explicitTab = asTab(searchParams.get("tab"));
  const defaultTab: TabKey =
    stream.status === "completed" ? "report" : "progress";
  const tab = explicitTab ?? defaultTab;

  const setTab = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", next);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const viewReport = useCallback(() => setTab("report"), [setTab]);

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[20rem_1fr]">
      {/* Left: run controls (sticky on desktop). */}
      <aside className="lg:sticky lg:top-8 lg:self-start">
        <div className="flex flex-col gap-3 rounded-lg border p-4">
          <h2 className="text-sm font-semibold">Research run</h2>
          {latestLoading ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <RunControlPanel
              sessionId={sessionId}
              view={stream.view}
              hasRun={hasRun}
              onRunStarted={setActiveRunId}
              onViewReport={viewReport}
            />
          )}
        </div>
      </aside>

      {/* Right: tabbed work area. */}
      <Tabs value={tab} onValueChange={setTab} className="min-w-0">
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="progress">Progress</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
          <TabsTrigger value="chat">Chat</TabsTrigger>
        </TabsList>

        <TabsContent value="progress">
          <WorkflowProgress
            view={stream.view}
            isReconnecting={stream.isReconnecting}
            hasRun={hasRun}
            onViewReport={viewReport}
          />
        </TabsContent>

        <TabsContent value="report">
          <ReportPanel
            sessionId={sessionId}
            runCompleted={stream.status === "completed"}
          />
        </TabsContent>

        <TabsContent value="chat">
          <p className="text-muted-foreground rounded-lg border border-dashed py-12 text-center text-sm">
            Follow-up chat arrives in Part 5.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );
}
