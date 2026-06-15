"use client";

import { ErrorState } from "@/components/error-state";

export default function SessionsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      title="Couldn't load sessions"
      description="We hit a snag loading your research sessions. Try again."
      error={error}
      reset={reset}
    />
  );
}
