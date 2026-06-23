/**
 * Follow-up chat state: RTK Query history is the source of truth for completed
 * messages; the in-flight assistant reply streams over SSE and is overlaid onto
 * the matching history row as tokens arrive. A refresh mid-generation auto-resumes
 * the stream (it finds the persisted `streaming` message and reattaches with
 * `since_seq`), so reloading never loses or duplicates the reply.
 *
 * To make streaming visible without waiting for a history refetch, we keep
 * optimistic placeholders for the just-sent user message and its assistant reply
 * — tokens render against the placeholder until the real row arrives.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { env } from "@/lib/env";
import { toApiError } from "@/lib/api-error";
import { openChatStream } from "@/lib/sse";
import { toastError } from "@/lib/toast";
import {
  useGetChatHistoryQuery,
  usePostChatMutation,
  useRetryChatMutation,
} from "@/services/chat";
import type { ChatMessage } from "@/types/chat";

export interface UseChatStreamResult {
  messages: ChatMessage[];
  isLoading: boolean;
  isStreaming: boolean;
  isSending: boolean;
  send: (content: string) => Promise<void>;
  retry: () => Promise<void>;
}

interface Pending {
  userId: string;
  userContent: string;
  assistantId: string;
  createdAt: string;
}

export function useChatStream(
  sessionId: string,
  { enabled = true }: { enabled?: boolean } = {},
): UseChatStreamResult {
  const { data, isLoading, refetch } = useGetChatHistoryQuery(sessionId, {
    skip: !enabled,
  });
  const [postChat, { isLoading: isPosting }] = usePostChatMutation();
  const [retryChat] = useRetryChatMutation();

  const [liveText, setLiveText] = useState<Record<string, string>>({});
  const [activeId, setActiveId] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const closeRef = useRef<(() => void) | null>(null);
  const startedRef = useRef<Set<string>>(new Set());

  const items = data?.items ?? [];

  const beginStream = useCallback(
    (messageId: string, sinceSeq: number) => {
      closeRef.current?.();
      startedRef.current.add(messageId);
      setActiveId(messageId);
      setLiveText((prev) => ({ ...prev, [messageId]: prev[messageId] ?? "" }));

      const url = `${env.NEXT_PUBLIC_API_BASE_URL}/api/sessions/${sessionId}/chat/${messageId}/stream`;
      closeRef.current = openChatStream(url, {
        sinceSeq,
        onDelta: ({ text }) =>
          setLiveText((prev) => ({
            ...prev,
            [messageId]: (prev[messageId] ?? "") + text,
          })),
        onDone: (done) => {
          setActiveId(null);
          setPending(null);
          if (done.status === "failed") {
            toastError("The assistant couldn't answer", {
              description: done.error?.message,
            });
          }
          // Pull the persisted final content + citations.
          void refetch();
        },
      });
    },
    [sessionId, refetch],
  );

  // Resume an in-flight reply after a refresh (persisted `streaming` message).
  useEffect(() => {
    const streaming = items.find(
      (m) => m.role === "assistant" && m.status === "streaming",
    );
    if (streaming && !startedRef.current.has(streaming.id)) {
      beginStream(streaming.id, 0);
    }
  }, [items, beginStream]);

  // Close the stream on unmount.
  useEffect(() => () => closeRef.current?.(), []);

  const send = useCallback(
    async (content: string) => {
      try {
        const { messageId } = await postChat({ sessionId, content }).unwrap();
        // Start streaming immediately so tokens render without waiting on
        // the history refetch. The optimistic placeholder below keeps the
        // streamed text visible until the real row arrives.
        setPending({
          userId: `pending-user-${messageId}`,
          userContent: content,
          assistantId: messageId,
          createdAt: new Date().toISOString(),
        });
        beginStream(messageId, 0);
        void refetch();
      } catch (e) {
        toastError("Couldn't send message", {
          description: toApiError(e).message,
        });
      }
    },
    [postChat, sessionId, refetch, beginStream],
  );

  const retry = useCallback(async () => {
    const lastAssistant = [...items]
      .reverse()
      .find((m) => m.role === "assistant");
    if (!lastAssistant) return;
    try {
      const { messageId } = await retryChat({
        sessionId,
        messageId: lastAssistant.id,
      }).unwrap();
      beginStream(messageId, 0);
      void refetch();
    } catch (e) {
      toastError("Couldn't retry", { description: toApiError(e).message });
    }
  }, [items, retryChat, sessionId, refetch, beginStream]);

  // Overlay live tokens onto the matching (still-streaming/empty) history row,
  // and synthesize placeholders for the just-sent pair until refetch lands.
  const messages: ChatMessage[] = useMemo(() => {
    const overlaid = items.map((m) => {
      const live = liveText[m.id];
      if (live != null && (m.status === "streaming" || !m.content)) {
        return { ...m, content: live, status: "streaming" as const };
      }
      return m;
    });
    if (!pending) return overlaid;
    // Once the assistant row (real server id) lands, the user row is also in
    // history — drop both optimistic placeholders. The assistant overlay above
    // already streams tokens onto the real row.
    const assistantLanded = overlaid.some((m) => m.id === pending.assistantId);
    if (assistantLanded) return overlaid;
    const extras: ChatMessage[] = [
      {
        id: pending.userId,
        sessionId,
        role: "user",
        content: pending.userContent,
        citations: [],
        createdAt: pending.createdAt,
        finishedAt: pending.createdAt,
        status: "complete",
        model: null,
        tokensIn: null,
        tokensOut: null,
        costUsd: null,
        error: null,
      },
      {
        id: pending.assistantId,
        sessionId,
        role: "assistant",
        content: liveText[pending.assistantId] ?? "",
        citations: [],
        createdAt: pending.createdAt,
        finishedAt: null,
        status: "streaming",
        model: null,
        tokensIn: null,
        tokensOut: null,
        costUsd: null,
        error: null,
      },
    ];
    return [...overlaid, ...extras];
  }, [items, liveText, pending, sessionId]);

  return {
    messages,
    isLoading,
    isStreaming: activeId !== null,
    isSending: isPosting || activeId !== null,
    send,
    retry,
  };
}
