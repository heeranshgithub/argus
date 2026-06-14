import { api } from "@/services/api";
import type { HealthResponse } from "@/types/api";

export const healthApi = api.injectEndpoints({
  endpoints: (build) => ({
    getHealth: build.query<HealthResponse, void>({
      query: () => "/api/health",
    }),
  }),
  overrideExisting: false,
});

export const { useGetHealthQuery } = healthApi;
