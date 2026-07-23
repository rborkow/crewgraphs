import {
  isHoneypotSubmission,
  validateCorrectionSubmission
} from "@/lib/corrections-model";
import {
  insertCorrectionSubmission,
  resolveCorrectionOrganizationId
} from "@/lib/corrections-data";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { ok: false, errors: { body: ["Request body must be valid JSON."] } },
      { status: 400 }
    );
  }

  if (isHoneypotSubmission(body)) {
    return Response.json({ ok: true });
  }

  const result = validateCorrectionSubmission(body);
  if (!result.success) {
    return Response.json({ ok: false, errors: result.errors }, { status: 400 });
  }

  try {
    const organizationId = await resolveCorrectionOrganizationId(result.data.org_slug);
    await insertCorrectionSubmission(result.data, organizationId);
    return Response.json({ ok: true }, { status: 201 });
  } catch {
    return Response.json({ ok: false }, { status: 500 });
  }
}
