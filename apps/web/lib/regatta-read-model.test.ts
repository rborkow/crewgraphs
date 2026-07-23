import { describe, expect, it } from "vitest";
import type { ResultRef } from "@crewgraphs/contracts";
import {
  formatRaceSeconds,
  formatResultValue,
  groupRegattaActivity,
  type RegattaResultRow
} from "@/lib/regatta-read-model";

function ref(overrides: Partial<ResultRef> = {}): ResultRef {
  return {
    value: 423.35,
    unit: "seconds",
    season: 2026,
    quality_state: "verified",
    source: {
      source_key: "herenow",
      regatta_external_key: "21464",
      event_external_key: "5.TT",
      provider_url: "https://legacy.herenow.com/results/#/races/21464/results"
    },
    retrieved_at: "2026-07-23T12:00:00Z",
    parser_version: "herenow-2026.07.1",
    ...overrides
  };
}

function row(overrides: Partial<RegattaResultRow> = {}): RegattaResultRow {
  return {
    season: 2026,
    regatta_key: "herenow:21464",
    regatta_name: "Cromwell Cup",
    regatta_date: "2026-07-19",
    venue: "Charles River, Cambridge, MA",
    source_key: "herenow",
    event_key: "5.TT",
    event_name: "Mens Masters 1x 50+",
    boat_class: "1x",
    round: "TT",
    crew_label: null,
    crew: [{ role: "stroke", name: "Andrew O'Brien" }],
    metric_key: "finish_time",
    status: "finished",
    source_ref: ref(),
    ...overrides
  };
}

describe("groupRegattaActivity", () => {
  it("collapses metric rows onto one entry line and orders seasons desc", () => {
    const seasons = groupRegattaActivity([
      row(),
      row({ metric_key: "place", source_ref: ref({ value: 1, unit: "rank" }) }),
      row({
        season: 2025,
        regatta_key: "time_team:usrowing-youth-national/2025",
        regatta_name: "Youth Nationals",
        source_key: "time_team",
        source_ref: ref({
          season: 2025,
          source: {
            source_key: "time_team",
            regatta_external_key: "usrowing-youth-national/2025",
            event_external_key: "abc",
            provider_url: null
          }
        })
      })
    ]);

    expect(seasons.map((s) => s.season)).toEqual([2026, 2025]);
    const entry = seasons[0].regattas[0].entries[0];
    expect(entry.metrics.finish_time?.value).toBe(423.35);
    expect(entry.metrics.place?.value).toBe(1);
    expect(entry.crew).toEqual([{ role: "stroke", name: "Andrew O'Brien" }]);
  });

  it("throws on a malformed source_ref rather than rendering it", () => {
    expect(() => groupRegattaActivity([row({ source_ref: { nope: true } })])).toThrow();
  });

  it("keeps separate crew labels as separate lines", () => {
    const seasons = groupRegattaActivity([
      row({ crew_label: "A" }),
      row({ crew_label: "B", source_ref: ref({ value: 431.02 }) })
    ]);
    expect(seasons[0].regattas[0].entries).toHaveLength(2);
  });
});

describe("formatters", () => {
  it("formats race seconds", () => {
    expect(formatRaceSeconds(423.35)).toBe("7:03.35");
    expect(formatRaceSeconds(3723.45)).toBe("1:02:03.45");
    expect(formatRaceSeconds(59.9)).toBe("0:59.90");
  });

  it("formats by unit", () => {
    expect(formatResultValue(ref({ value: 1, unit: "rank" }))).toBe("1st");
    expect(formatResultValue(ref({ value: 22, unit: "rank" }))).toBe("22nd");
    expect(formatResultValue(ref({ value: 13, unit: "rank" }))).toBe("13th");
    expect(formatResultValue(ref({ value: 13.37, unit: "margin_seconds" }))).toBe("+0:13.37");
    expect(formatResultValue(ref({ value: null }))).toBe("—");
  });
});
