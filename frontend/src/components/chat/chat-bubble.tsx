"use client";

import { RotateCw } from "lucide-react";

import { ChatCitations } from "@/components/chat/chat-citations";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-1" aria-label="Assistant is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  );
}

/**
 * One chat message bubble — user (right, filled) or assistant (left, muted).
 * Shows a typing indicator while an empty assistant reply streams, citation
 * chips once it lands, and an inline Retry on a failed reply (PLAN §1.1).
 */
export function ChatBubble({
  message,
  onCite,
  onRetry,
}: {
  message: ChatMessage;
  onCite: (url: string) => void;
  onRetry?: () => void;
}) {
  const isUser = message.role === "user";
  const streaming = message.status === "streaming";
  const failed = message.status === "failed";

  return (
    <div className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap break-words",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
          failed && "bg-destructive/10 text-destructive",
        )}
      >
        {message.content ? (
          <>
            {message.content}
            {streaming && (
              <span className="ml-0.5 inline-block animate-pulse" aria-hidden>
                ▍
              </span>
            )}
          </>
        ) : streaming ? (
          <TypingDots />
        ) : failed ? (
          <span>{message.error?.message ?? "Failed to generate a reply."}</span>
        ) : null}
      </div>

      {!isUser && <ChatCitations citations={message.citations} onCite={onCite} />}

      <div className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
        <time dateTime={message.createdAt}>{formatClock(message.createdAt)}</time>
        {failed && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 font-medium text-foreground hover:underline focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <RotateCw className="size-3" aria-hidden />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
