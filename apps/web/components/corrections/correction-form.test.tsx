import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CorrectionForm } from "./correction-form";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CorrectionForm", () => {
  it("renders the resolved organization and submits into the success state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 201,
        headers: { "content-type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CorrectionForm
        orgSlug="millbrook-community-rowing"
        orgDisplayName="Millbrook Community Rowing"
      />
    );

    expect(screen.getByText("Millbrook Community Rowing")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("What figure or field?"), {
      target: { value: "FY2024 total revenue" }
    });
    fireEvent.change(screen.getByLabelText("What should we review?"), {
      target: { value: "The source filing has another value." }
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "rower@example.com" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit correction" }));

    await waitFor(() => {
      expect(screen.getByText("Thank you for flagging it.")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/corrections",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          org_slug: "millbrook-community-rowing",
          field_reference: "FY2024 total revenue",
          message: "The source filing has another value.",
          submitter_email: "rower@example.com",
          website: ""
        })
      })
    );
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });
});
