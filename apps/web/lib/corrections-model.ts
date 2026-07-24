import { z } from "zod";

const optionalText = (maxLength: number) =>
  z.preprocess(
    (value) => (typeof value === "string" && value.trim() === "" ? undefined : value),
    z.string().trim().max(maxLength).optional()
  );

export const correctionSubmissionSchema = z.object({
  org_slug: optionalText(200),
  field_reference: optionalText(500),
  message: z.string().trim().min(1, "Tell us what should be corrected.").max(4000),
  submitter_email: z.preprocess(
    (value) => (typeof value === "string" && value.trim() === "" ? undefined : value),
    z
      .string()
      .trim()
      .max(320)
      .email("Enter a valid email address.")
      .optional()
  ),
  website: z.string().optional()
});

export type CorrectionSubmission = z.infer<typeof correctionSubmissionSchema>;
export type CorrectionFieldErrors = Partial<Record<keyof CorrectionSubmission, string[]>>;

export function isHoneypotSubmission(body: unknown): boolean {
  if (typeof body !== "object" || body === null || Array.isArray(body)) return false;
  const website = (body as Record<string, unknown>).website;
  return typeof website === "string" && website.length > 0;
}

export function validateCorrectionSubmission(
  body: unknown
):
  | { success: true; data: CorrectionSubmission }
  | { success: false; errors: CorrectionFieldErrors } {
  const result = correctionSubmissionSchema.safeParse(body);
  if (result.success) return result;
  return { success: false, errors: result.error.flatten().fieldErrors };
}

export function correctionDetails(
  submission: Pick<CorrectionSubmission, "org_slug" | "field_reference">
): { org_slug?: string; field_reference?: string } {
  return {
    ...(submission.org_slug ? { org_slug: submission.org_slug } : {}),
    ...(submission.field_reference ? { field_reference: submission.field_reference } : {})
  };
}
