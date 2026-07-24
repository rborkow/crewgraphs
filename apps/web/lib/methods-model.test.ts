import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { CONCEPT_MAP, CONCEPT_MAP_VERSION } from "@/lib/concept-map";
import {
  eligibilityConditions,
  mapMetricCatalog,
  mapSourceRegistry
} from "@/lib/methods-model";

function metricPayload(overrides: Record<string, unknown> = {}) {
  return {
    key: "operating_margin",
    version: 1,
    label: "Operating margin",
    description: "(Total revenue − total expenses) ÷ total revenue, per fiscal year.",
    unit: "percent",
    eligibility_rule: { requires_positive: ["total_revenue"] },
    limitation: "A single year can swing on one-time gifts.",
    ...overrides
  };
}

describe("mapMetricCatalog", () => {
  it("validates payloads and sorts by label", () => {
    const catalog = mapMetricCatalog([
      metricPayload({ key: "revenue_cagr", label: "Revenue growth (CAGR)" }),
      metricPayload()
    ]);
    expect(catalog.map((metric) => metric.key)).toEqual(["operating_margin", "revenue_cagr"]);
  });

  it("keeps only the newest version per metric key", () => {
    const catalog = mapMetricCatalog([
      metricPayload({ version: 2, description: "v2 definition" }),
      metricPayload({ version: 1, description: "v1 definition" })
    ]);
    expect(catalog).toHaveLength(1);
    expect(catalog[0].version).toBe(2);
    expect(catalog[0].description).toBe("v2 definition");
  });

  it("throws on a payload that fails the contract", () => {
    expect(() => mapMetricCatalog([metricPayload({ version: "one" })])).toThrow();
  });
});

describe("eligibilityConditions", () => {
  it("spells out the known rule kinds", () => {
    expect(
      eligibilityConditions({
        min_observations: 3,
        requires_positive: ["total_revenue"],
        requires_resolved: ["membership_dues"]
      })
    ).toEqual([
      "At least 3 comparable annual observations.",
      "Total revenue must be positive in that fiscal year.",
      "Membership dues must be reported on the filing (not absent)."
    ]);
  });

  it("names an unknown rule instead of hiding it", () => {
    expect(eligibilityConditions({ max_gap_years: 2 })).toEqual(["Rule max_gap_years: 2."]);
  });
});

describe("mapSourceRegistry", () => {
  const payload = { description: "desc", attribution: "attr" };

  it("orders known sources canonically regardless of input order", () => {
    const registry = mapSourceRegistry([
      { source_key: "propublica", payload },
      { source_key: "irs_990_xml", payload },
      { source_key: "givingtuesday", payload }
    ]);
    expect(registry.map((entry) => entry.source_key)).toEqual([
      "irs_990_xml",
      "givingtuesday",
      "propublica"
    ]);
    expect(registry[0].display_name).toBe("IRS Form 990 / 990-EZ e-file");
  });

  it("keeps an unknown source visible after the known ones", () => {
    const registry = mapSourceRegistry([
      { source_key: "new_source", payload },
      { source_key: "irs_bmf", payload }
    ]);
    expect(registry.map((entry) => entry.source_key)).toEqual(["irs_bmf", "new_source"]);
    expect(registry[1].display_name).toBe("new_source");
  });

  it("throws on a payload that fails the contract", () => {
    expect(() =>
      mapSourceRegistry([{ source_key: "irs_bmf", payload: { description: "only" } }])
    ).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Drift guard: the /methods concept table is a transcription of the pipeline's
// concept map. If the YAML changes without this table (or vice versa), fail.
// ---------------------------------------------------------------------------

describe("concept map transcription", () => {
  const yamlPath = repoFile(
    path.join("pipeline", "src", "crewgraphs", "concept_map", `${CONCEPT_MAP_VERSION}.yaml`)
  );
  const yaml = fs.readFileSync(yamlPath, "utf8");

  it("matches the pipeline concept map version", () => {
    expect(yaml).toContain(`version: ${CONCEPT_MAP_VERSION}`);
  });

  it("covers every concept in the pipeline map, and no extras", () => {
    const yamlConcepts = [...yaml.matchAll(/- concept: (\w+)/g)].map((match) => match[1]);
    expect(new Set(CONCEPT_MAP.map((entry) => entry.key))).toEqual(new Set(yamlConcepts));
    expect(CONCEPT_MAP).toHaveLength(yamlConcepts.length);
  });

  it("lists only XML elements that appear in the pipeline map", () => {
    for (const entry of CONCEPT_MAP) {
      for (const element of [...entry.form990, ...entry.form990ez]) {
        expect(yaml, `${entry.key}: ${element}`).toContain(element);
      }
    }
  });

  it("marks a concept form-unavailable only when the map does", () => {
    for (const entry of CONCEPT_MAP) {
      const block = yaml.split(`- concept: ${entry.key}\n`)[1]?.split("- concept:")[0] ?? "";
      expect(block.includes(`"990EZ": null`), `${entry.key} 990-EZ availability`).toBe(
        entry.form990ez.length === 0
      );
    }
  });
});

function repoFile(relative: string): string {
  let dir = process.cwd();
  for (let depth = 0; depth < 6; depth++) {
    const candidate = path.join(dir, relative);
    if (fs.existsSync(candidate)) return candidate;
    dir = path.dirname(dir);
  }
  throw new Error(`Could not locate ${relative} walking up from ${process.cwd()}`);
}
