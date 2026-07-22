import { directoryBlobSchema, type DirectoryBlob } from "@crewgraphs/contracts";
import directoryJson from "../../../db/fixtures/directory.json";

/**
 * The published directory blob. In production this is served from KV behind the
 * `publish:current` pointer; for the design foundation we read the fixture blob
 * so the tokens and identicons are exercised against real org shapes.
 *
 * Parsed once at module scope through the shared contract — drift in the
 * fixture fails loudly at build time rather than rendering a broken directory.
 */
export const directory: DirectoryBlob = directoryBlobSchema.parse(directoryJson);
