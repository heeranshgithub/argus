"use client";

import { Paperclip, SendHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { chatMessageSchema } from "@/schemas/chat";

/**
 * Multi-line composer: Enter to send, Shift+Enter for a newline. The attach
 * button is a reserved (disabled) future hook (PLAN_PART_5 §1.1). Hidden in print.
 */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (content: string) => void;
  disabled?: boolean;
}) {
  const parsed = chatMessageSchema.safeParse({ content: value });
  const canSend = parsed.success && !disabled;

  function submit() {
    if (!parsed.success) return;
    onSubmit(parsed.data.content);
  }

  return (
    <div className="sticky bottom-0 flex items-end gap-2 border-t bg-background/95 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur print:hidden">
      <Button
        type="button"
        size="icon"
        variant="ghost"
        disabled
        aria-label="Attach a file (coming soon)"
        title="Attach a file (coming soon)"
        className="shrink-0"
      >
        <Paperclip className="size-4" aria-hidden />
      </Button>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Ask a follow-up about this company…"
        aria-label="Message"
        disabled={disabled}
        className="max-h-40 min-h-10 flex-1 resize-none"
      />
      <Button
        type="button"
        size="icon"
        onClick={submit}
        disabled={!canSend}
        aria-label="Send message"
        className="shrink-0"
      >
        <SendHorizontal className="size-4" aria-hidden />
      </Button>
    </div>
  );
}
