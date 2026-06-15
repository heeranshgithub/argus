"use client";

import { ErrorState } from "@/components/error-state";

export default function SessionDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      title="Couldn't load this session"
      description="Something went wrong loading the session workspace. Try again."
      error={error}
      reset={reset}
    />
  );
}
