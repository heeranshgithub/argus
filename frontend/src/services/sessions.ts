import { api } from "@/services/api";
import type { SessionCreateInput } from "@/schemas/session";
import type { Session, SessionListResponse } from "@/types/session";

interface ListArgs {
  limit?: number;
  skip?: number;
}

export const sessionsApi = api.injectEndpoints({
  endpoints: (build) => ({
    getSessions: build.query<SessionListResponse, ListArgs | void>({
      query: (args) => {
        const { limit = 20, skip = 0 } = args ?? {};
        return { url: "/api/sessions", params: { limit, skip } };
      },
      providesTags: (result) =>
        result
          ? [
              ...result.items.map((s) => ({ type: "Session" as const, id: s.id })),
              { type: "Session" as const, id: "LIST" },
            ]
          : [{ type: "Session" as const, id: "LIST" }],
    }),
    getSession: build.query<Session, string>({
      query: (id) => `/api/sessions/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Session", id }],
    }),
    createSession: build.mutation<Session, SessionCreateInput>({
      query: (body) => ({ url: "/api/sessions", method: "POST", body }),
      invalidatesTags: [{ type: "Session", id: "LIST" }],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetSessionsQuery,
  useGetSessionQuery,
  useCreateSessionMutation,
} = sessionsApi;
