// Runtime drift detection for backend responses. The TS types are hand-mirrored from
// the backend, so a backend change silently breaks the UI. These zod schemas assert the
// ESSENTIAL fields the UI depends on (passthrough allows the rest) and `validate()` is
// NON-FATAL — it logs a console warning on drift and returns the data unchanged, so a
// schema lag never takes down the dashboard.
import { z } from "zod";

export const JobSchema = z
  .object({
    id: z.number(),
    title: z.string(),
    status: z.enum(["Active", "Archived"]),
  })
  .passthrough();

export const CandidateSchema = z
  .object({
    id: z.number(),
    status: z.string(),
    total_score: z.number(),
  })
  .passthrough();

export function validate<T>(schema: z.ZodTypeAny, data: T, label: string): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    // eslint-disable-next-line no-console
    console.warn(`[api] ${label} response shape drift:`, result.error.issues.slice(0, 3));
  }
  return data;
}

export function validateEach<T>(schema: z.ZodTypeAny, items: T[], label: string): T[] {
  if (Array.isArray(items) && items.length) validate(schema, items[0], `${label}[0]`);
  return items;
}
