/**
 * Follow-up chat state: RTK Query history is the source of truth for completed
 * messages; the in-flight assistant reply streams over SSE and is overlaid onto
 * the matching history row as tokens arrive. A refresh mid-generation auto-resumes
 * the stream (it finds the persisted `streaming` message and reattaches with
 * `since_seq`), so reloading never loses or duplicates the reply.
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
  const closeRef = useRef<(() => void) | null>(null);
  const startedRef = useRef<Set<string>>(new Set());

  const items = useMemo(() => data?.items ?? [], [data]);

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
        await refetch();
        beginStream(messageId, 0);
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
      await refetch();
      beginStream(messageId, 0);
    } catch (e) {
      toastError("Couldn't retry", { description: toApiError(e).message });
    }
  }, [items, retryChat, sessionId, refetch, beginStream]);

  // Overlay live tokens onto the matching (still-streaming/empty) history row.
  const messages: ChatMessage[] = items.map((m) => {
    const live = liveText[m.id];
    if (live != null && (m.status === "streaming" || !m.content)) {
      return { ...m, content: live, status: "streaming" };
    }
    return m;
  });

  return {
    messages,
    isLoading,
    isStreaming: activeId !== null,
    isSending: isPosting || activeId !== null,
    send,
    retry,
  };
}
