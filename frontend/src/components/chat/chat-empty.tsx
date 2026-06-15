"use client";

import { MessagesSquare } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Shown in the Chat tab before a report exists — chat is grounded in the report,
 * so it directs the user to run research first (PLAN_PART_5 §1.1).
 */
export function ChatEmpty({ onGoToProgress }: { onGoToProgress: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-16 text-center">
      <MessagesSquare className="size-8 text-muted-foreground" aria-hidden />
      <div className="space-y-1">
        <p className="text-sm font-medium">Run research first to unlock chat</p>
        <p className="text-muted-foreground text-sm">
          Follow-up chat answers questions grounded in the generated report.
        </p>
      </div>
      <Button size="sm" variant="outline" onClick={onGoToProgress}>
        Go to Progress
      </Button>
    </div>
  );
}
