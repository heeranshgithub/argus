"use client";

import { useState } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatEmpty } from "@/components/chat/chat-empty";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatSuggestedPrompts } from "@/components/chat/chat-suggested-prompts";
import { Skeleton } from "@/components/ui/skeleton";
import { useChatStream } from "@/hooks/use-chat-stream";
import { useGetChatSuggestionsQuery } from "@/services/chat";

/**
 * The Chat tab: empty-state gate until a report exists, then suggested prompts +
 * message list + composer. Citation chips call ``onCitation`` to cross-link to
 * the Report tab's source cards (PLAN_PART_5 §1).
 */
export function ChatTab({
  sessionId,
  reportReady,
  onCitation,
  onGoToProgress,
}: {
  sessionId: string;
  reportReady: boolean;
  onCitation: (url: string) => void;
  onGoToProgress: () => void;
}) {
  const chat = useChatStream(sessionId, { enabled: reportReady });
  const { data: suggestions } = useGetChatSuggestionsQuery(sessionId, {
    skip: !reportReady,
  });
  const [draft, setDraft] = useState("");

  if (!reportReady) {
    return <ChatEmpty onGoToProgress={onGoToProgress} />;
  }

  function handleSend(content: string) {
    void chat.send(content);
    setDraft("");
  }

  const showSuggestions =
    !chat.isLoading &&
    chat.messages.length === 0 &&
    (suggestions?.suggestions.length ?? 0) > 0;

  return (
    <div className="flex min-h-[28rem] flex-col gap-4">
      <div className="flex-1">
        {chat.isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-12 w-2/3" />
            <Skeleton className="ml-auto h-12 w-1/2" />
          </div>
        ) : chat.messages.length ? (
          <ChatMessageList
            messages={chat.messages}
            onCite={onCitation}
            onRetry={() => void chat.retry()}
          />
        ) : (
          <p className="text-muted-foreground py-8 text-center text-sm">
            Ask anything about this company — answers are grounded in the report
            with citations.
          </p>
        )}
      </div>

      {showSuggestions && (
        <ChatSuggestedPrompts
          prompts={suggestions!.suggestions}
          onPick={setDraft}
        />
      )}

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={handleSend}
        disabled={chat.isSending}
      />
    </div>
  );
}
