import { z } from "zod";

/**
 * Validation for an outbound chat message. Mirrors the backend `ChatCreate`
 * constraints (1–4000 chars) so the composer rejects empties before the round-trip.
 */
export const chatMessageSchema = z.object({
  content: z
    .string()
    .trim()
    .min(1, "Type a message first")
    .max(4000, "Message must be at most 4000 characters"),
});

export type ChatMessageInput = z.infer<typeof chatMessageSchema>;
