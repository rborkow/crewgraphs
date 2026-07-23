export interface AdminCounts {
  pendingCorrections: number;
  openReviewTasks: number;
}

export interface AdminCorrectionRow {
  id: string;
  created_at: Date | string;
  organization_id: string | null;
  org_display_name: string | null;
  org_slug: string | null;
  message: string;
  details: unknown;
  status: string;
}

export interface AdminReviewTaskRow {
  id: string;
  entity_type: string;
  entity_id: string;
  task_type: string;
  status: string;
  assigned_to: string | null;
  details: unknown;
  created_at: Date | string;
}

export interface AdminAuditEventRow {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before: unknown;
  after: unknown;
  reversal_of_event_id: string | null;
  occurred_at: Date | string;
}

export function parseDatabaseCount(value: string | number | undefined): number {
  if (typeof value === "number") return value;
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function adminDate(value: Date | string): { iso: string; label: string } {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return { iso: String(value), label: String(value) };
  return {
    iso: date.toISOString(),
    label: new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC"
    }).format(date)
  };
}

export function detailsText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}
