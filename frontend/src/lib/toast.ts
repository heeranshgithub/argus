/**
 * Toast helpers with built-in de-duplication (PLAN_PART_5 §2.2).
 *
 * Identical error messages within a 3s window collapse into a single toast (via
 * a stable id keyed on the message), so a burst of the same failure — e.g. an
 * SSE flapping offline — never stacks. The global visible cap is set on the
 * `<Toaster visibleToasts={3} />`.
 */

import { toast } from "sonner";

const DEDUPE_WINDOW_MS = 3000;
const recent = new Map<string, number>();

export function toastError(
  message: string,
  options?: { description?: string },
): void {
  const now = Date.now();
  const last = recent.get(message);
  if (last && now - last < DEDUPE_WINDOW_MS) return;
  recent.set(message, now);
  toast.error(message, { id: `err:${message}`, ...options });
}

export function toastSuccess(
  message: string,
  options?: { description?: string },
): void {
  toast.success(message, options);
}
