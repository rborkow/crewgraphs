import { describe, expect, it } from "vitest";
import {
  adminDate,
  detailsText,
  parseDatabaseCount,
  statusLabel
} from "@/lib/admin-model";

describe("admin model", () => {
  it("normalizes bigint counts returned as strings", () => {
    expect(parseDatabaseCount("12")).toBe(12);
    expect(parseDatabaseCount(undefined)).toBe(0);
  });

  it("formats dates in stable UTC and details as readable JSON", () => {
    expect(adminDate("2026-07-23T14:30:00Z")).toEqual({
      iso: "2026-07-23T14:30:00.000Z",
      label: "Jul 23, 2026, 2:30 PM"
    });
    expect(detailsText({ field_reference: "FY2024 revenue" })).toContain(
      '"field_reference": "FY2024 revenue"'
    );
  });

  it("turns database statuses into plain labels", () => {
    expect(statusLabel("in_progress")).toBe("in progress");
  });
});
