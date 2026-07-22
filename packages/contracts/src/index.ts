import { z } from "zod";

export const sourceRefSchema = z.object({
  value: z.number().nullable(),
  unit: z.enum(["USD", "count"]),
  period: z.object({
    fy_end: z.iso.date(),
    label: z.string()
  }),
  quality_state: z.enum(["verified", "derived", "partial", "unavailable", "under_review"]),
  source: z.object({
    source_key: z.string(),
    form_type: z.enum(["990", "990EZ", "990N"]),
    filing_id: z.string(),
    source_path: z.string(),
    raw_url: z.string().url().nullable()
  }),
  retrieved_at: z.string(),
  parser_version: z.string(),
  metric: z.object({
    key: z.string(),
    version: z.number()
  }).nullable()
});

export type SourceRef = z.infer<typeof sourceRefSchema>;
