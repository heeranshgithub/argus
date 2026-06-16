"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { ChatBubble } from "@/components/chat/chat-bubble";
import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/types/chat";

/**
 * Scrolling list of chat bubbles (oldest → newest). Does NOT auto-scroll during
 * streaming — the user stays where they are and can click the ↓ button to jump
 * to the latest message when it finishes.
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
  const [atBottom, setAtBottom] = useState(true);

  // Track whether the end sentinel is visible in the viewport.
  useEffect(() => {
    const el = endRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setAtBottom(entry?.isIntersecting ?? false),
      { threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const scrollToBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  const lastAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === "assistant")?.id;

  return (
    <>
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

      {/* Scroll-to-bottom button — appears when user has scrolled away from the end */}
      {!atBottom && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-10 flex justify-center">
          <Button
            size="icon"
            variant="secondary"
            aria-label="Scroll to bottom"
            onClick={scrollToBottom}
            className="pointer-events-auto size-8 rounded-full shadow-lg ring-1 ring-border"
          >
            <ChevronDown className="size-4" />
          </Button>
        </div>
      )}
    </>
  );
}
