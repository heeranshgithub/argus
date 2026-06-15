import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import { env } from "@/lib/env";

/**
 * Root RTK Query API. Feature endpoints are injected per-file via
 * `injectEndpoints` to keep concerns split. Tag types are declared up front
 * and used for cache invalidation in later parts.
 */
export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({ baseUrl: env.NEXT_PUBLIC_API_BASE_URL }),
  tagTypes: ["Session", "Run", "Report", "Chat"],
  endpoints: () => ({}),
});
