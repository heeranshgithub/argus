import type { ApiError } from "@/types/api";

export interface NormalizedApiError {
  code: string;
  message: string;
}

function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiError).error?.code === "string"
  );
}

/**
 * Normalize an RTK Query error (or anything) into the standard `{ code, message }`
 * shape from the backend error contract, falling back gracefully when the body
 * isn't a recognizable envelope.
 */
export function toApiError(error: unknown): NormalizedApiError {
  // RTK Query's FetchBaseQueryError carries the parsed body on `.data`.
  const data =
    typeof error === "object" && error !== null && "data" in error
      ? (error as { data: unknown }).data
      : error;

  if (isApiError(data)) {
    return { code: data.error.code, message: data.error.message };
  }

  return {
    code: "unknown_error",
    message: "Something went wrong. Please try again.",
  };
}
