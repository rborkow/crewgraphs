import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/corrections-data", () => ({
  resolveCorrectionOrganizationId: vi.fn(),
  insertCorrectionSubmission: vi.fn()
}));

import { POST } from "./route";
import {
  insertCorrectionSubmission,
  resolveCorrectionOrganizationId
} from "@/lib/corrections-data";

function correctionRequest(body: unknown): Request {
  return new Request("https://crewgraphs.test/api/corrections", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/corrections", () => {
  it("resolves and inserts a valid correction", async () => {
    vi.mocked(resolveCorrectionOrganizationId).mockResolvedValue("org-1");

    const response = await POST(
      correctionRequest({
        org_slug: "millbrook-community-rowing",
        field_reference: "FY2024 total revenue",
        message: "The filing reports a different total.",
        submitter_email: "rower@example.com"
      })
    );

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ ok: true });
    expect(insertCorrectionSubmission).toHaveBeenCalledWith(
      expect.objectContaining({
        org_slug: "millbrook-community-rowing",
        field_reference: "FY2024 total revenue",
        message: "The filing reports a different total.",
        submitter_email: "rower@example.com"
      }),
      "org-1"
    );
  });

  it("returns success for a filled honeypot without touching data", async () => {
    const response = await POST(correctionRequest({ website: "spam", message: "" }));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true });
    expect(resolveCorrectionOrganizationId).not.toHaveBeenCalled();
    expect(insertCorrectionSubmission).not.toHaveBeenCalled();
  });

  it("returns field errors for invalid input", async () => {
    const response = await POST(
      correctionRequest({ message: "", submitter_email: "not-an-email" })
    );

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      ok: false,
      errors: {
        message: ["Tell us what should be corrected."],
        submitter_email: ["Enter a valid email address."]
      }
    });
    expect(insertCorrectionSubmission).not.toHaveBeenCalled();
  });

  it("inserts a null organization id when the slug cannot be resolved", async () => {
    vi.mocked(resolveCorrectionOrganizationId).mockResolvedValue(null);

    const response = await POST(
      correctionRequest({
        org_slug: "unknown-club",
        message: "This organization reference needs review."
      })
    );

    expect(response.status).toBe(201);
    expect(insertCorrectionSubmission).toHaveBeenCalledWith(
      expect.objectContaining({ org_slug: "unknown-club" }),
      null
    );
  });
});
