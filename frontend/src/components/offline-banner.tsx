"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

/**
 * A slim banner shown while the browser is offline (PLAN_PART_5 §2.2). SSE
 * reconnection backoff is paused independently in `lib/sse` via `navigator.onLine`.
 */
export function OfflineBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 bg-destructive px-4 py-1.5 text-center text-xs font-medium text-white print:hidden"
    >
      <WifiOff className="size-3.5" aria-hidden />
      You&apos;re offline — live updates are paused until your connection returns.
    </div>
  );
}
