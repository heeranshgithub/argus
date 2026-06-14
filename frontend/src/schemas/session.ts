import { z } from "zod";

/**
 * Validation for the create-session form. Mirrors the backend `SessionCreate`
 * constraints so the client rejects bad input before it hits the API.
 */
export const sessionCreateSchema = z.object({
  companyName: z
    .string()
    .trim()
    .min(1, "Company name is required")
    .max(200, "Company name must be at most 200 characters"),
  website: z.string().trim().url("Enter a valid URL (including https://)"),
  objective: z
    .string()
    .trim()
    .min(1, "Objective is required")
    .max(2000, "Objective must be at most 2000 characters"),
});

export type SessionCreateInput = z.infer<typeof sessionCreateSchema>;
