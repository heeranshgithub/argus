"use client";

import { hostOf } from "@/lib/url";
import type { Citation } from "@/types/chat";

/**
 * The citations row under an assistant message. Each chip links back to the
 * matching source card in the Report tab (PLAN_PART_5 §1.1).
 */
export function ChatCitations({
  citations,
  onCite,
}: {
  citations: Citation[];
  onCite: (url: string) => void;
}) {
  if (!citations.length) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5 print:hidden" aria-label="Sources cited">
      {citations.map((citation) => (
        <li key={citation.sourceIndex}>
          <button
            type="button"
            onClick={() => onCite(citation.url)}
            title={citation.title}
            className="flex max-w-[14rem] items-center gap-1 rounded-full border bg-background px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <span className="font-semibold text-foreground">
              [{citation.sourceIndex}]
            </span>
            <span className="truncate">{hostOf(citation.url)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
