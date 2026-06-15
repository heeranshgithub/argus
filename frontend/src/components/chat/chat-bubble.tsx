"use client";

import { RotateCw } from "lucide-react";

import { ChatCitations } from "@/components/chat/chat-citations";
import { ChatMarkdown } from "@/components/chat/chat-markdown";
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
 * Assistant content is rendered as markdown (headings, lists, bold, links,
 * code, tables); user content stays as plain text. A typing indicator shows
 * while an empty assistant reply is being requested, a soft caret blinks at
 * the tail of partial tokens, and a Retry button surfaces on failed replies.
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
  const hasContent = Boolean(message.content);

  return (
    <div className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm break-words",
          isUser
            ? "bg-primary whitespace-pre-wrap text-primary-foreground"
            : "bg-muted text-foreground",
          failed && "bg-destructive/10 text-destructive",
        )}
      >
        {hasContent ? (
          isUser ? (
            <>{message.content}</>
          ) : (
            <div className="relative">
              <ChatMarkdown content={message.content} />
              {streaming && (
                <span
                  className="ml-0.5 inline-block h-3.5 w-[2px] -translate-y-[1px] animate-pulse rounded-sm bg-foreground/70 align-middle"
                  aria-hidden
                />
              )}
            </div>
          )
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
