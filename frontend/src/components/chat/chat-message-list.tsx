"use client";

import { useEffect, useRef } from "react";

import { ChatBubble } from "@/components/chat/chat-bubble";
import type { ChatMessage } from "@/types/chat";

/**
 * Scrolling list of chat bubbles (oldest → newest), auto-scrolling to the bottom
 * as messages arrive/stream. Announced politely to screen readers (PLAN §3).
 */
export function ChatMessageList({
  messages,
  onCite,
  onRetry,
}: {
  messages: ChatMessage[];
  onCite: (url: string) => void;
  onRetry: () => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  // Re-scroll on any content change (new message or a streaming token).
  const tail = messages.at(-1);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, tail?.content, tail?.status]);

  const lastAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === "assistant")?.id;

  return (
    <div
      role="log"
      aria-live="polite"
      aria-label="Conversation"
      className="flex flex-col gap-4"
    >
      {messages.map((message) => (
        <ChatBubble
          key={message.id}
          message={message}
          onCite={onCite}
          onRetry={
            message.id === lastAssistantId && message.status === "failed"
              ? onRetry
              : undefined
          }
        />
      ))}
      <div ref={endRef} />
    </div>
  );
}
