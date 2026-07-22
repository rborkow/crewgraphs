import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { sourceRefSchema } from "../src/index";

const outputDirectory = fileURLToPath(new URL("../schemas/", import.meta.url));
mkdirSync(outputDirectory, { recursive: true });

const schema = z.toJSONSchema(sourceRefSchema, { target: "draft-2020-12" });
writeFileSync(`${outputDirectory}source-ref.v0.schema.json`, `${JSON.stringify(schema, null, 2)}\n`);
