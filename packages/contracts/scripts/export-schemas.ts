import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import {
  directoryBlobSchema,
  orgProfilePayloadSchema,
  orgRegattaPayloadSchema,
  resultRefSchema,
  sourceRefSchema
} from "../src/index";

const outputDirectory = fileURLToPath(new URL("../schemas/", import.meta.url));
mkdirSync(outputDirectory, { recursive: true });

const schemaExports: Array<[string, z.ZodType]> = [
  ["source-ref.v1.schema.json", sourceRefSchema],
  ["org-profile-payload.v1.schema.json", orgProfilePayloadSchema],
  ["directory-blob.v1.schema.json", directoryBlobSchema],
  ["result-ref.v1.schema.json", resultRefSchema],
  ["org-regatta-payload.v1.schema.json", orgRegattaPayloadSchema]
];

for (const [filename, schema] of schemaExports) {
  const jsonSchema = z.toJSONSchema(schema, { target: "draft-2020-12", io: "input" });
  writeFileSync(`${outputDirectory}${filename}`, `${JSON.stringify(jsonSchema, null, 2)}\n`);
  console.log(`wrote schemas/${filename}`);
}
