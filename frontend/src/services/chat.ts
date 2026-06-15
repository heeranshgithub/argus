import { api } from "@/services/api";
import type {
  ChatAccepted,
  ChatListResponse,
  ChatSuggestions,
} from "@/types/chat";

/**
 * RTK Query endpoints for follow-up chat.
 *
 * History is the source of truth for completed messages; the live assistant
 * reply is streamed over SSE (see `hooks/use-chat-stream`), not polled. These
 * endpoints cover the request/response edges: loading history, posting a
 * question, retrying the last reply, and the starter suggestions.
 */
export const chatApi = api.injectEndpoints({
  endpoints: (build) => ({
    getChatHistory: build.query<ChatListResponse, string>({
      query: (sessionId) => `/api/sessions/${sessionId}/chat`,
      providesTags: (_result, _error, sessionId) => [
        { type: "Chat", id: sessionId },
      ],
    }),

    postChat: build.mutation<ChatAccepted, { sessionId: string; content: string }>({
      query: ({ sessionId, content }) => ({
        url: `/api/sessions/${sessionId}/chat`,
        method: "POST",
        body: { content },
      }),
    }),

    retryChat: build.mutation<
      ChatAccepted,
      { sessionId: string; messageId: string }
    >({
      query: ({ sessionId, messageId }) => ({
        url: `/api/sessions/${sessionId}/chat/${messageId}/retry`,
        method: "POST",
      }),
    }),

    getChatSuggestions: build.query<ChatSuggestions, string>({
      query: (sessionId) => `/api/sessions/${sessionId}/chat/suggestions`,
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetChatHistoryQuery,
  usePostChatMutation,
  useRetryChatMutation,
  useGetChatSuggestionsQuery,
} = chatApi;
