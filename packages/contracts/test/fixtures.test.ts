import { readdir, readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { directoryBlobSchema, orgProfilePayloadSchema } from "../src";

const fixturesDir = new URL("../../../db/fixtures/", import.meta.url);
const payloadsDir = new URL("./payloads/", fixturesDir);

describe("Phase 1 fixture cohort", () => {
  it("parses every profile payload", async () => {
    const files = (await readdir(payloadsDir)).filter((file) => file.endsWith(".json")).sort();
    expect(files).toHaveLength(12);

    for (const file of files) {
      const payload = JSON.parse(await readFile(new URL(file, payloadsDir), "utf8"));
      expect(() => orgProfilePayloadSchema.parse(payload), file).not.toThrow();
    }
  });

  it("parses the directory blob and matches payload slugs one-to-one", async () => {
    const directory = directoryBlobSchema.parse(JSON.parse(await readFile(new URL("./directory.json", fixturesDir), "utf8")));
    const files = (await readdir(payloadsDir)).filter((file) => file.endsWith(".json")).sort();
    const payloads = await Promise.all(files.map(async (file) => JSON.parse(await readFile(new URL(file, payloadsDir), "utf8"))));
    const payloadSlugs = payloads.map((payload) => payload.slug).sort();
    const directorySlugs = directory.entries.map((entry) => entry.slug).sort();

    expect(directory.entries).toHaveLength(12);
    expect(directorySlugs).toEqual(payloadSlugs);
    expect(new Set(directorySlugs).size).toBe(12);
  });
});
