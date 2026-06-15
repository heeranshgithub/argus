import { api } from "@/services/api";
import type { Report } from "@/types/report";
import type {
  RunAccepted,
  RunListResponse,
  WorkflowRun,
  WorkflowRunSummary,
} from "@/types/workflow";

/**
 * RTK Query endpoints for workflow runs + the generated report.
 *
 * The live timeline is driven by SSE (see `hooks/use-run-stream`), not polling —
 * these endpoints cover the request/response edges: starting/resuming a run,
 * seeding first paint (`getRun`), discovering the latest run, and fetching the
 * report once a run completes.
 */
export const runsApi = api.injectEndpoints({
  endpoints: (build) => ({
    startRun: build.mutation<RunAccepted, string>({
      query: (sessionId) => ({
        url: `/api/sessions/${sessionId}/run`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, sessionId) => [
        { type: "Session", id: sessionId },
        { type: "Run", id: "LIST" },
      ],
    }),

    resumeRun: build.mutation<RunAccepted, string>({
      query: (sessionId) => ({
        url: `/api/sessions/${sessionId}/run/resume`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, sessionId) => [
        { type: "Session", id: sessionId },
        { type: "Run", id: "LIST" },
      ],
    }),

    getRun: build.query<WorkflowRun, { sessionId: string; runId: string }>({
      query: ({ sessionId, runId }) =>
        `/api/sessions/${sessionId}/runs/${runId}`,
      providesTags: (_result, _error, { runId }) => [{ type: "Run", id: runId }],
    }),

    /** Most recent run for a session (summary, no events), or null if none. */
    getLatestRun: build.query<WorkflowRunSummary | null, string>({
      query: (sessionId) => ({
        url: `/api/sessions/${sessionId}/runs`,
        params: { limit: 1, skip: 0 },
      }),
      transformResponse: (response: RunListResponse) =>
        response.items[0] ?? null,
      providesTags: (result) =>
        result
          ? [
              { type: "Run", id: result.id },
              { type: "Run", id: "LIST" },
            ]
          : [{ type: "Run", id: "LIST" }],
    }),

    getReport: build.query<Report, string>({
      query: (sessionId) => `/api/sessions/${sessionId}/report`,
      providesTags: (_result, _error, sessionId) => [
        { type: "Report", id: sessionId },
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useStartRunMutation,
  useResumeRunMutation,
  useGetRunQuery,
  useGetLatestRunQuery,
  useGetReportQuery,
  useLazyGetReportQuery,
} = runsApi;
