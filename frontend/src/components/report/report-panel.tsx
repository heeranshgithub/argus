"use client";

import { ReportEmpty } from "@/components/report/report-empty";
import { ReportLoading } from "@/components/report/report-loading";
import { ReportView } from "@/components/report/report-view";
import { toApiError } from "@/lib/api-error";
import { useGetReportQuery } from "@/services/runs";

/**
 * Connects the report query to the view. The backend 404s until a run completes,
 * which we treat as the natural "not generated yet" empty state rather than an
 * error. `runCompleted` lets us distinguish "never run" from the rare
 * completed-but-missing case.
 */
export function ReportPanel({
  sessionId,
  runCompleted,
}: {
  sessionId: string;
  runCompleted: boolean;
}) {
  const { data, error, isLoading } = useGetReportQuery(sessionId);

  if (isLoading) return <ReportLoading />;

  if (data) return <ReportView report={data} />;

  if (error) {
    const code = toApiError(error).code;
    if (code === "report_not_found") {
      return (
        <ReportEmpty
          message={
            runCompleted
              ? "Report not found — please re-run the research."
              : "Run research to generate a report."
          }
        />
      );
    }
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        Could not load the report. Please try again.
      </div>
    );
  }

  return <ReportEmpty />;
}
