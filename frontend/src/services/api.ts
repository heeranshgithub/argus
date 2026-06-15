import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import { env } from "@/lib/env";
import { setLastRequestId } from "@/lib/request-id";

/** Wrap fetch to record each response's request id for error correlation. */
const trackedFetch: typeof fetch = async (input, init) => {
  const response = await fetch(input, init);
  const requestId = response.headers.get("x-request-id");
  if (requestId) setLastRequestId(requestId);
  return response;
};

/**
 * Root RTK Query API. Feature endpoints are injected per-file via
 * `injectEndpoints` to keep concerns split. Tag types are declared up front
 * and used for cache invalidation in later parts.
 */
export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: env.NEXT_PUBLIC_API_BASE_URL,
    fetchFn: trackedFetch,
  }),
  tagTypes: ["Session", "Run", "Report", "Chat"],
  endpoints: () => ({}),
});
