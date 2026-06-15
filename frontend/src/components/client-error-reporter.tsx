"use client";

import { useEffect } from "react";

import { env } from "@/lib/env";
import { getLastRequestId } from "@/lib/request-id";

/**
 * Captures unhandled errors + promise rejections and POSTs them to
 * `/api/client-errors` (PLAN_PART_5 §2.3). Best-effort and fire-and-forget — it
 * never throws, and failures to report are swallowed.
 */
export function ClientErrorReporter() {
  useEffect(() => {
    function report(message: string, stack?: string) {
      const body = JSON.stringify({
        message: message.slice(0, 2000),
        stack: stack?.slice(0, 8000),
        url: window.location.href,
        userAgent: navigator.userAgent,
        requestId: getLastRequestId(),
      });
      void fetch(`${env.NEXT_PUBLIC_API_BASE_URL}/api/client-errors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => {
        /* reporting is best-effort */
      });
    }

    const onError = (event: ErrorEvent) =>
      report(event.message, event.error?.stack);
    const onRejection = (event: PromiseRejectionEvent) =>
      report(
        `Unhandled rejection: ${String(event.reason)}`,
        event.reason?.stack,
      );

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}
