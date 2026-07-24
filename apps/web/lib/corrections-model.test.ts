import { describe, expect, it } from "vitest";
import {
  correctionDetails,
  isHoneypotSubmission,
  validateCorrectionSubmission
} from "@/lib/corrections-model";

describe("corrections model", () => {
  it("trims a valid submission and omits blank optional values", () => {
    const result = validateCorrectionSubmission({
      org_slug: " millbrook-community-rowing ",
      field_reference: " ",
      message: " The FY2024 total looks wrong. ",
      submitter_email: ""
    });

    expect(result).toEqual({
      success: true,
      data: {
        org_slug: "millbrook-community-rowing",
        field_reference: undefined,
        message: "The FY2024 total looks wrong.",
        submitter_email: undefined
      }
    });
    if (result.success) {
      expect(correctionDetails(result.data)).toEqual({
        org_slug: "millbrook-community-rowing"
      });
    }
  });

  it("reports message and email field errors", () => {
    const result = validateCorrectionSubmission({
      message: " ",
      submitter_email: "not-an-email"
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.errors.message).toBeDefined();
      expect(result.errors.submitter_email).toEqual(["Enter a valid email address."]);
    }
  });

  it("recognizes only a non-empty website honeypot", () => {
    expect(isHoneypotSubmission({ website: "https://spam.test" })).toBe(true);
    expect(isHoneypotSubmission({ website: " " })).toBe(true);
    expect(isHoneypotSubmission({ website: "" })).toBe(false);
    expect(isHoneypotSubmission(null)).toBe(false);
  });
});
