import { formatDistanceToNow } from "date-fns";

/** Human-friendly relative time, e.g. "3 hours ago". */
export function formatRelative(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return formatDistanceToNow(date, { addSuffix: true });
}
