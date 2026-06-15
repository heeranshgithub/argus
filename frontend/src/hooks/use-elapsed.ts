"use client";

import { useEffect, useState } from "react";

/**
 * Live elapsed milliseconds since `startIso`, ticking once a second while
 * `active`. When inactive (or no start), it stops re-rendering and reports the
 * frozen span (or 0). Used for the running-node and overall run timers.
 */
export function useElapsed(
  startIso: string | undefined,
  active: boolean,
): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active) return;
    // Tick immediately (via timeout, not synchronously) then once a second.
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [active]);

  if (!startIso) return 0;
  const start = new Date(startIso).getTime();
  if (Number.isNaN(start)) return 0;
  return Math.max(0, now - start);
}
