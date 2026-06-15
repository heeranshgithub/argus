"use client";

import { Sparkles } from "lucide-react";

/**
 * Three starter chips (LLM-generated from the report). Clicking one pre-fills the
 * composer rather than sending immediately (PLAN_PART_5 §1.1).
 */
export function ChatSuggestedPrompts({
  prompts,
  onPick,
}: {
  prompts: string[];
  onPick: (prompt: string) => void;
}) {
  if (!prompts.length) return null;
  return (
    <div className="flex flex-col gap-2 print:hidden">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Sparkles className="size-3.5" aria-hidden />
        Suggested questions
      </p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onPick(prompt)}
            className="rounded-full border px-3 py-1.5 text-left text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
