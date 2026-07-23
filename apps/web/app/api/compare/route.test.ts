import { describe, expect, it, vi } from "vitest";
import { fixtureDirectory } from "@/test/fixtures";

vi.mock("@/lib/directory", () => ({
  getDirectory: vi.fn(async () => fixtureDirectory)
}));

vi.mock("@/lib/compare-data", () => ({
  getCompareSeries: vi.fn(async () => [])
}));

import { GET } from "./route";
import { getCompareSeries } from "@/lib/compare-data";

describe("GET /api/compare", () => {
  it("returns a CSV download and applies the latest-common-year default", async () => {
    const response = await GET(
      new Request(
        "https://crewgraphs.test/api/compare?orgs=millbrook-community-rowing,harborview-scholastic-oars"
      )
    );

    expect(response.headers.get("content-type")).toBe("text/csv; charset=utf-8");
    expect(response.headers.get("content-disposition")).toContain("fy2024");
    expect(await response.text()).toBe(
      "org,series_key,label,tax_year,fiscal_year_end,value,quality_state,is_amended,source_path\r\n"
    );
    expect(getCompareSeries).toHaveBeenCalledWith(
      fixtureDirectory.snapshot_id,
      expect.any(Array),
      2024
    );
  });
});
