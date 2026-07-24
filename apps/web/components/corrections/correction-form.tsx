"use client";

import { useState, type FormEvent } from "react";

interface CorrectionFormProps {
  orgSlug?: string;
  orgDisplayName?: string;
}

type SubmissionState = "idle" | "pending" | "success" | "error";

export function CorrectionForm({ orgSlug, orgDisplayName }: CorrectionFormProps) {
  const [state, setState] = useState<SubmissionState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("pending");
    setErrorMessage("");

    const form = new FormData(event.currentTarget);
    const payload = {
      ...(orgSlug ? { org_slug: orgSlug } : {}),
      field_reference: String(form.get("field_reference") ?? ""),
      message: String(form.get("message") ?? ""),
      submitter_email: String(form.get("submitter_email") ?? ""),
      website: String(form.get("website") ?? "")
    };

    try {
      const response = await fetch("/api/corrections", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
          | { errors?: Record<string, string[]> }
          | null;
        const firstError = body?.errors ? Object.values(body.errors).flat()[0] : undefined;
        throw new Error(firstError ?? "We could not submit this report. Please try again.");
      }

      setState("success");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "We could not submit this report. Please try again."
      );
      setState("error");
    }
  }

  if (state === "success") {
    return (
      <section
        aria-live="polite"
        className="rounded-md border border-mist bg-surface p-5 sm:p-6"
      >
        <p className="eyebrow">Report received</p>
        <h2 className="display mt-2 text-2xl text-river">Thank you for flagging it.</h2>
        <p className="mt-3 max-w-xl text-sm text-muted">
          A person will review the source and our extraction. Corrections are resolved through the
          audited curation process.
        </p>
      </section>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5 rounded-md border border-mist bg-surface p-5 sm:p-6">
      {orgSlug ? (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-faint">Organization</p>
          <p className="mt-1 text-sm font-medium text-river">
            {orgDisplayName ?? orgSlug}
          </p>
          {!orgDisplayName ? (
            <p className="mt-1 text-xs text-muted">
              This organization is not in the current directory; its reference will still be
              included with the report.
            </p>
          ) : null}
        </div>
      ) : null}

      <div>
        <label htmlFor="field_reference" className="block text-sm font-medium text-river">
          What figure or field?
        </label>
        <p id="field-reference-help" className="mt-1 text-xs text-muted">
          Optional. A label, tax year, or section helps us find it.
        </p>
        <input
          id="field_reference"
          name="field_reference"
          type="text"
          aria-describedby="field-reference-help"
          className="mt-2 w-full rounded-md border border-mist bg-paper px-3 py-2 text-sm text-river"
        />
      </div>

      <div>
        <label htmlFor="message" className="block text-sm font-medium text-river">
          What should we review?
        </label>
        <textarea
          id="message"
          name="message"
          required
          minLength={1}
          maxLength={4000}
          rows={7}
          className="mt-2 w-full rounded-md border border-mist bg-paper px-3 py-2 text-sm text-river"
        />
      </div>

      <div>
        <label htmlFor="submitter_email" className="block text-sm font-medium text-river">
          Email
        </label>
        <p id="email-help" className="mt-1 text-xs text-muted">
          Optional. Used only to contact you about this report; it is never shown publicly.
        </p>
        <input
          id="submitter_email"
          name="submitter_email"
          type="email"
          maxLength={320}
          autoComplete="email"
          aria-describedby="email-help"
          className="mt-2 w-full rounded-md border border-mist bg-paper px-3 py-2 text-sm text-river"
        />
      </div>

      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="website">Website</label>
        <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      {state === "error" ? (
        <p role="alert" className="text-sm text-buoy-ink">
          {errorMessage}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={state === "pending"}
        className="inline-flex items-center justify-center rounded-sm border border-buoy px-4 py-2 text-sm font-medium text-buoy-ink transition-colors hover:bg-buoy hover:text-paper disabled:cursor-wait disabled:opacity-60"
      >
        {state === "pending" ? "Submitting…" : "Submit correction"}
      </button>
    </form>
  );
}
