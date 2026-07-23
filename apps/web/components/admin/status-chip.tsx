import { statusLabel } from "@/lib/admin-model";

const ACTIVE_STATUSES = new Set(["pending", "open", "in_progress"]);

export function AdminStatusChip({ status }: { status: string }) {
  const active = ACTIVE_STATUSES.has(status);
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
        active ? "border-buoy text-buoy-ink" : "border-mist text-muted"
      }`}
    >
      {statusLabel(status)}
    </span>
  );
}
